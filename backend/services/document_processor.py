from typing import List, Dict, Any, Optional, BinaryIO
import uuid
import re
from datetime import datetime
import logging
import io
import pdfplumber
from docx import Document as DocxDocument
from models import PolicyDocument, PolicyChunk
from services.embedding_service import EmbeddingService
from services.milvus_service import MilvusService
from config import settings

logger = logging.getLogger(__name__)


class DocumentProcessor:
    def __init__(self, embedding_service: EmbeddingService, milvus_service: MilvusService):
        self.embedding_service = embedding_service
        self.milvus_service = milvus_service
        self.chunk_size = settings.chunk_size
        self.chunk_overlap = settings.chunk_overlap
    
    def extract_text_from_pdf(self, file_content: bytes) -> str:
        """Extract text from PDF file"""
        try:
            text_content = []
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)
            
            full_text = '\n\n'.join(text_content)
            logger.info(f"Extracted {len(full_text)} characters from PDF with {len(text_content)} pages")
            return full_text
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")
    
    def extract_text_from_docx(self, file_content: bytes) -> str:
        """Extract text from DOCX file"""
        try:
            doc = DocxDocument(io.BytesIO(file_content))
            text_content = []
            
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_content.append(paragraph.text)
            
            full_text = '\n\n'.join(text_content)
            logger.info(f"Extracted {len(full_text)} characters from DOCX")
            return full_text
        except Exception as e:
            logger.error(f"Error extracting text from DOCX: {e}")
            raise ValueError(f"Failed to extract text from DOCX: {str(e)}")
    
    def extract_text_from_file(self, file_content: bytes, filename: str) -> str:
        """Extract text from various file formats"""
        file_ext = filename.lower().split('.')[-1]
        
        if file_ext == 'pdf':
            return self.extract_text_from_pdf(file_content)
        elif file_ext in ['docx', 'doc']:
            return self.extract_text_from_docx(file_content)
        elif file_ext == 'txt':
            return file_content.decode('utf-8')
        else:
            raise ValueError(f"Unsupported file format: {file_ext}")
    
    def process_document(self, document: PolicyDocument) -> List[PolicyChunk]:
        """Process a document: chunk it, generate embeddings, and store in Milvus"""
        
        # Extract sections and chunk
        chunks = self._chunk_document(document)
        
        # Generate embeddings
        texts = [chunk.text for chunk in chunks]
        embeddings = self.embedding_service.generate_embeddings(texts)
        
        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        
        # Store in Milvus
        milvus_chunks = [self._chunk_to_dict(chunk) for chunk in chunks]
        self.milvus_service.insert_policy_chunks(milvus_chunks)
        
        logger.info(f"Processed document {document.doc_id}: {len(chunks)} chunks created")
        return chunks
    
    def _chunk_document(self, document: PolicyDocument) -> List[PolicyChunk]:
        """Split document into overlapping chunks with section context"""
        chunks = []
        
        # Try to detect sections
        sections = self._detect_sections(document.content)
        
        if sections:
            # Chunk within sections
            for section_title, section_text in sections:
                section_chunks = self._create_chunks(section_text, document, section_title)
                chunks.extend(section_chunks)
        else:
            # No sections detected, chunk the entire document
            chunks = self._create_chunks(document.content, document)
        
        return chunks
    
    def _detect_sections(self, text: str) -> List[tuple]:
        """Detect sections in the document"""
        sections = []
        
        # Match common section patterns
        # Pattern 1: "Section 1.1: Title" or "1.1 Title"
        # Pattern 2: "Article 5: Title"
        # Pattern 3: Headers with capital letters
        
        lines = text.split('\n')
        current_section = None
        current_text = []
        
        section_pattern = r'^(?:Section|Article|Chapter|\d+\.?\d*)\s+.*?:?\s*$'
        
        for line in lines:
            if re.match(section_pattern, line.strip(), re.IGNORECASE):
                # Save previous section
                if current_section:
                    sections.append((current_section, '\n'.join(current_text)))
                
                # Start new section
                current_section = line.strip()
                current_text = []
            else:
                current_text.append(line)
        
        # Add last section
        if current_section:
            sections.append((current_section, '\n'.join(current_text)))
        
        return sections if sections else []
    
    def _create_chunks(
        self, 
        text: str, 
        document: PolicyDocument, 
        section: str = None
    ) -> List[PolicyChunk]:
        """Create overlapping chunks from text"""
        chunks = []
        
        # Split by words to respect word boundaries
        words = text.split()
        
        start = 0
        chunk_index = 0
        
        while start < len(words):
            end = start + self.chunk_size
            chunk_words = words[start:end]
            chunk_text = ' '.join(chunk_words)
            
            # Skip very short chunks
            if len(chunk_text.strip()) < 50:
                break
            
            chunk_id = f"{document.doc_id}_chunk_{chunk_index}"
            
            chunk = PolicyChunk(
                chunk_id=chunk_id,
                doc_id=document.doc_id,
                text=chunk_text,
                doc_title=document.title,
                section=section,
                source=document.source,
                topic=document.topic,
                version=document.version,
                valid_from=document.valid_from,
                valid_to=document.valid_to,
                is_active=document.is_active
            )
            
            chunks.append(chunk)
            
            start += (self.chunk_size - self.chunk_overlap)
            chunk_index += 1
        
        return chunks
    
    def _chunk_to_dict(self, chunk: PolicyChunk) -> Dict[str, Any]:
        """Convert PolicyChunk to dict for Milvus insertion"""
        return {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "text": chunk.text[:4000],  # Truncate to max length
            "embedding": chunk.embedding,
            "doc_title": chunk.doc_title[:500],
            "section": (chunk.section or "")[:200],
            "source": chunk.source.value,
            "topic": chunk.topic.value,
            "version": chunk.version,
            "is_active": chunk.is_active,
            "valid_from": chunk.valid_from
        }
    
    def update_document(self, old_doc_id: str, new_document: PolicyDocument) -> Dict[str, Any]:
        """Update a document and detect changes"""
        
        # Deactivate old version
        self.milvus_service.deactivate_document_chunks(old_doc_id)
        
        # Process new version
        new_chunks = self.process_document(new_document)
        
        # For MVP, we'll log the change
        change_info = {
            "doc_id": new_document.doc_id,
            "old_version": "previous",
            "new_version": new_document.version,
            "changes_detected": ["Document updated with new content"],
            "timestamp": datetime.now()
        }
        
        logger.info(f"Document updated: {old_doc_id} -> {new_document.doc_id}")
        return change_info
