from typing import Dict, Any
from datetime import datetime
import logging
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generate PDF audit reports for compliance decisions"""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))
        
        # Section header style
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#374151'),
            spaceAfter=12,
            spaceBefore=12
        ))
        
        # Body style
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['BodyText'],
            fontSize=11,
            textColor=colors.HexColor('#4b5563'),
            alignment=TA_JUSTIFY,
            spaceAfter=12
        ))
    
    def generate_decision_report(self, decision_data: Dict[str, Any]) -> bytes:
        """Generate PDF audit report for a decision"""
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            story = []
            
            # Extract data
            trace_id = decision_data.get("trace_id", "N/A")
            transaction = decision_data.get("transaction", {})
            decision = decision_data.get("decision", {})
            reasoning = decision.get("reasoning", {})
            timestamp = decision_data.get("timestamp", datetime.now().isoformat())
            
            # Title
            title = Paragraph("Compliance Decision Audit Report", self.styles['CustomTitle'])
            story.append(title)
            story.append(Spacer(1, 0.3*inch))
            
            # Report metadata
            metadata_data = [
                ['Report Generated:', datetime.now().strftime('%Y-%m-%d %H:%M:%S')],
                ['Trace ID:', trace_id],
                ['Decision Timestamp:', timestamp],
            ]
            metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
            metadata_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1f2937')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db'))
            ]))
            story.append(metadata_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Transaction Details
            story.append(Paragraph("Transaction Details", self.styles['SectionHeader']))
            
            tx_data = [
                ['Transaction ID:', transaction.get('transaction_id', 'N/A')],
                ['Amount:', f"{transaction.get('amount', 0):,.2f} {transaction.get('currency', 'USD')}"],
                ['Type:', transaction.get('type', 'N/A')],
                ['From Account:', transaction.get('from_account', 'N/A')],
                ['To Account:', transaction.get('to_account', 'N/A')],
                ['Country:', transaction.get('country', 'N/A')],
                ['Description:', transaction.get('description', 'N/A')],
            ]
            
            tx_table = Table(tx_data, colWidths=[2*inch, 4*inch])
            tx_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1f2937')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db'))
            ]))
            story.append(tx_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Compliance Decision
            story.append(Paragraph("Compliance Decision", self.styles['SectionHeader']))
            
            verdict = decision.get('verdict', 'N/A')
            risk_level = decision.get('risk_level', 'N/A')
            risk_score = decision.get('risk_score', 0)
            
            # Color code verdict
            verdict_color = colors.HexColor('#dc2626') if verdict == 'FLAG' else \
                           colors.HexColor('#f59e0b') if verdict == 'NEEDS_REVIEW' else \
                           colors.HexColor('#16a34a')
            
            decision_data_list = [
                ['Verdict:', verdict],
                ['Risk Level:', risk_level],
                ['Risk Score:', f"{risk_score:.2f}"],
                ['Confidence:', f"{decision.get('confidence', 0):.2%}"],
            ]
            
            decision_table = Table(decision_data_list, colWidths=[2*inch, 4*inch])
            decision_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1f2937')),
                ('TEXTCOLOR', (1, 0), (1, 0), verdict_color),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db'))
            ]))
            story.append(decision_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Reasoning
            story.append(Paragraph("Decision Reasoning", self.styles['SectionHeader']))
            reasoning_text = reasoning.get('explanation', 'No explanation provided.')
            story.append(Paragraph(reasoning_text, self.styles['CustomBody']))
            story.append(Spacer(1, 0.2*inch))
            
            # Policy Citations
            citations = reasoning.get('citations', [])
            if citations:
                story.append(Paragraph("Policy Citations", self.styles['SectionHeader']))
                
                for i, citation in enumerate(citations, 1):
                    citation_text = f"<b>[{i}]</b> {citation.get('doc_title', 'N/A')}"
                    if citation.get('section'):
                        citation_text += f" - {citation.get('section')}"
                    citation_text += f"<br/><i>Relevance: {citation.get('relevance_score', 0):.2%}</i>"
                    citation_text += f"<br/>{citation.get('text', '')[:200]}..."
                    
                    story.append(Paragraph(citation_text, self.styles['CustomBody']))
                    story.append(Spacer(1, 0.1*inch))
            
            # Similar Cases
            similar_cases = decision.get('similar_cases', [])
            if similar_cases:
                story.append(PageBreak())
                story.append(Paragraph("Similar Historical Cases", self.styles['SectionHeader']))
                
                for i, case in enumerate(similar_cases, 1):
                    case_text = f"<b>Case {i}:</b> {case.get('case_id', 'N/A')}"
                    case_text += f"<br/><b>Decision:</b> {case.get('decision', 'N/A')}"
                    case_text += f"<br/><b>Similarity:</b> {case.get('similarity_score', 0):.2%}"
                    case_text += f"<br/><i>{case.get('reasoning', '')[:200]}...</i>"
                    
                    story.append(Paragraph(case_text, self.styles['CustomBody']))
                    story.append(Spacer(1, 0.15*inch))
            
            # Footer
            story.append(Spacer(1, 0.3*inch))
            footer_text = "<i>This report is generated automatically by PolicyLens AI Compliance System. "
            footer_text += "All decisions should be reviewed by qualified compliance officers.</i>"
            story.append(Paragraph(footer_text, self.styles['CustomBody']))
            
            # Build PDF
            doc.build(story)
            
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Generated PDF audit report for trace_id: {trace_id}")
            return pdf_bytes
        
        except Exception as e:
            logger.error(f"Error generating PDF report: {e}")
            raise
    
    def generate_impact_report(self, impact_data: Dict[str, Any]) -> bytes:
        """Generate PDF report for policy change impact"""
        try:
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            story = []
            
            # Title
            title = Paragraph("Policy Change Impact Report", self.styles['CustomTitle'])
            story.append(title)
            story.append(Spacer(1, 0.3*inch))
            
            # Report metadata
            report_id = impact_data.get("report_id", "N/A")
            generated_at = impact_data.get("generated_at", datetime.now().isoformat())
            
            metadata_data = [
                ['Report ID:', report_id],
                ['Generated:', generated_at],
            ]
            metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
            metadata_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1f2937')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db'))
            ]))
            story.append(metadata_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Policy Change Summary
            policy_change = impact_data.get("policy_change", {})
            impact_summary = impact_data.get("impact_summary", {})
            
            story.append(Paragraph("Change Summary", self.styles['SectionHeader']))
            
            change_data_list = [
                ['Change Type:', policy_change.get('change_type', 'N/A')],
                ['Change Magnitude:', f"{policy_change.get('change_magnitude', 0):.2%}"],
                ['Decisions Affected:', str(impact_summary.get('decisions_affected', 0))],
                ['Requires Re-evaluation:', 'Yes' if impact_summary.get('requires_re_evaluation') else 'No'],
            ]
            
            change_table = Table(change_data_list, colWidths=[2*inch, 4*inch])
            change_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f3f4f6')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1f2937')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#d1d5db'))
            ]))
            story.append(change_table)
            story.append(Spacer(1, 0.3*inch))
            
            # Recommendations
            recommendations = impact_data.get("recommendations", [])
            if recommendations:
                story.append(Paragraph("Recommendations", self.styles['SectionHeader']))
                for rec in recommendations:
                    story.append(Paragraph(f"• {rec}", self.styles['CustomBody']))
                story.append(Spacer(1, 0.2*inch))
            
            # Affected Sections
            sections_affected = policy_change.get("sections_affected", [])
            if sections_affected:
                story.append(Paragraph("Affected Sections", self.styles['SectionHeader']))
                for section in sections_affected:
                    story.append(Paragraph(f"• {section}", self.styles['CustomBody']))
            
            # Build PDF
            doc.build(story)
            
            pdf_bytes = buffer.getvalue()
            buffer.close()
            
            logger.info(f"Generated PDF impact report: {report_id}")
            return pdf_bytes
        
        except Exception as e:
            logger.error(f"Error generating PDF impact report: {e}")
            raise
