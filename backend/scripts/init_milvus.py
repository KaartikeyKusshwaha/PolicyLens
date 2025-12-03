"""
Script to initialize Milvus with sample compliance policy documents
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.milvus_service import MilvusService
from services.embedding_service import EmbeddingService
from datetime import datetime
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_sample_policies():
    """Sample compliance policies for demonstration"""
    return [
        {
            "doc_id": "POL-AML-001",
            "doc_title": "Anti-Money Laundering Transaction Monitoring Guidelines",
            "version": "2.0",
            "source": "internal",
            "topic": "aml",
            "sections": [
                {
                    "section": "Transaction Thresholds",
                    "text": "All cash transactions exceeding USD 10,000 must be reported to the compliance team within 24 hours of detection. Transactions between USD 5,000 and USD 10,000 require enhanced monitoring. Enhanced due diligence (EDD) is mandatory for all transactions exceeding USD 50,000, including verification of source of funds and beneficial ownership."
                },
                {
                    "section": "Suspicious Activity Indicators",
                    "text": "Monitor for the following red flags: rapid movement of funds, structuring of transactions to avoid reporting thresholds, transactions with no clear business purpose, unusual transaction patterns inconsistent with customer profile, involvement of shell companies or offshore jurisdictions without legitimate business rationale."
                },
                {
                    "section": "Customer Risk Rating",
                    "text": "Customers are classified into Low, Medium, and High risk categories. High-risk customers include: Politically Exposed Persons (PEPs), customers from high-risk jurisdictions, cash-intensive businesses, non-resident customers, and customers with complex ownership structures. High-risk customers require EDD and approval from senior management for account opening."
                }
            ]
        },
        {
            "doc_id": "POL-SANCTIONS-001",
            "doc_title": "International Sanctions Compliance Policy",
            "version": "3.1",
            "source": "ofac",
            "topic": "sanctions",
            "sections": [
                {
                    "section": "Prohibited Jurisdictions",
                    "text": "The following jurisdictions are subject to comprehensive sanctions and all transactions are prohibited: North Korea (DPRK), Iran, Syria, and the Crimea region of Ukraine. Cuba and Venezuela are subject to partial sanctions. All transactions must be screened against OFAC Specially Designated Nationals (SDN) list, EU Consolidated List, and UK HMT sanctions list before processing."
                },
                {
                    "section": "Screening Requirements",
                    "text": "Real-time screening is mandatory for all transactions, customer onboarding, and wire transfers. Screening must cover customer names, beneficiaries, intermediary banks, and transaction descriptions. Any match (100% or fuzzy match above 95%) must be escalated to the compliance team immediately. False positives must be documented with clear rationale for clearance."
                },
                {
                    "section": "Trade-Based Sanctions",
                    "text": "Restrictions apply to trade in specific commodities and technologies. Prohibited items include military equipment, dual-use technology, luxury goods to sanctioned countries, oil and petroleum products from sanctioned jurisdictions, and goods involving forced labor. Documentary evidence is required for all international trade transactions."
                }
            ]
        },
        {
            "doc_id": "POL-KYC-001",
            "doc_title": "Know Your Customer (KYC) Requirements",
            "version": "1.8",
            "source": "internal",
            "topic": "kyc",
            "sections": [
                {
                    "section": "Identity Verification Standards",
                    "text": "Individual customers must provide: government-issued photo ID (passport, driver's license, or national ID card), proof of address dated within last 3 months (utility bill, bank statement), and tax identification number. For corporate customers: certificate of incorporation, register of directors and shareholders, beneficial ownership declaration (owners with 25%+ stake), business license, and board resolution authorizing account opening."
                },
                {
                    "section": "Enhanced Due Diligence (EDD)",
                    "text": "EDD is required for: PEPs and their family members/close associates, customers from high-risk jurisdictions (FATF blacklist), non-face-to-face customers, complex ownership structures with multiple layers, cash-intensive businesses, and correspondent banking relationships. EDD procedures include: source of wealth verification, purpose of account establishment, enhanced ongoing monitoring (monthly review), senior management approval."
                },
                {
                    "section": "Ongoing Monitoring",
                    "text": "Customer information must be reviewed and updated: Low-risk customers every 3 years, Medium-risk customers annually, High-risk customers every 6 months. Transaction monitoring must detect: unusual activity patterns, transactions inconsistent with business profile, dormant accounts with sudden activity, and rapid deposits followed by withdrawals. Any suspicious activity must be reported via SAR (Suspicious Activity Report) within 30 days."
                }
            ]
        },
        {
            "doc_id": "POL-FRAUD-001",
            "doc_title": "Fraud Prevention and Detection Policy",
            "version": "1.5",
            "source": "internal",
            "topic": "fraud",
            "sections": [
                {
                    "section": "Transaction Fraud Indicators",
                    "text": "Monitor for fraud indicators: sudden change in transaction patterns, multiple failed authentication attempts, transactions from unusual geographic locations, use of VPN or anonymizing services, mismatched IP geolocation and declared address, rapid account setup and transaction, and requests to bypass security procedures. High-risk indicators require immediate transaction hold and customer contact verification."
                },
                {
                    "section": "Account Takeover Prevention",
                    "text": "Implement multi-factor authentication (MFA) for all online transactions. Monitor for: login attempts from new devices, unusual login times, multiple failed login attempts, password reset requests followed by large transactions, changes to contact information or beneficiaries, and withdrawal of high balances shortly after account changes. Implement step-up authentication for high-risk activities."
                },
                {
                    "section": "Internal Fraud Controls",
                    "text": "Implement segregation of duties: no single employee can initiate and approve transactions, dual authorization required for transactions exceeding USD 25,000, maker-checker controls for customer information changes, regular access rights reviews, mandatory vacation policy (5+ consecutive days), and restriction on personal trading accounts. All system access must be logged and monitored."
                }
            ]
        },
        {
            "doc_id": "POL-PEP-001",
            "doc_title": "Politically Exposed Persons (PEP) Guidelines",
            "version": "2.2",
            "source": "internal",
            "topic": "kyc",
            "sections": [
                {
                    "section": "PEP Definition and Classification",
                    "text": "PEPs are individuals entrusted with prominent public functions: heads of state, senior politicians, senior government officials, judicial or military officials, executives of state-owned corporations, and important political party officials. Family members (spouse, parents, children, siblings) and known close associates are also classified as PEPs. PEP status remains active for 12 months after the individual leaves the prominent position."
                },
                {
                    "section": "PEP Due Diligence Requirements",
                    "text": "All PEP relationships require: senior management approval before account opening, enhanced due diligence including source of wealth verification, understanding of expected account activity and source of funds, ongoing monitoring with quarterly transaction reviews, immediate escalation of unusual activity, enhanced recordkeeping (maintain records for 7 years post-relationship), and annual relationship review by compliance officer."
                },
                {
                    "section": "PEP Red Flags",
                    "text": "Elevated risk indicators for PEPs: transactions inconsistent with known source of wealth, involvement of family members or close associates in transactions, use of complex corporate structures or nominees, transactions with countries known for corruption, large cash deposits or withdrawals, politically exposed business sectors (defense, natural resources, infrastructure contracts), and reluctance to provide information on source of funds."
                }
            ]
        }
    ]


def chunk_policy_sections(policy):
    """Convert policy sections into chunks for embedding"""
    chunks = []
    
    for section in policy["sections"]:
        chunk_id = f"{policy['doc_id']}-{uuid.uuid4().hex[:8]}"
        
        chunk = {
            "chunk_id": chunk_id,
            "doc_id": policy["doc_id"],
            "text": section["text"],
            "doc_title": policy["doc_title"],
            "section": section["section"],
            "source": policy["source"],
            "topic": policy["topic"],
            "version": policy["version"],
            "is_active": True,
            "valid_from": datetime.now()
        }
        chunks.append(chunk)
    
    return chunks


def initialize_milvus():
    """Initialize Milvus with sample policies"""
    logger.info("Starting Milvus initialization...")
    
    # Initialize services
    embedding_service = EmbeddingService()
    milvus_service = MilvusService()
    
    try:
        # Connect to Milvus
        logger.info("Connecting to Milvus...")
        milvus_service.connect()
        logger.info("✓ Connected to Milvus")
        
        # Get sample policies
        policies = get_sample_policies()
        logger.info(f"Loaded {len(policies)} sample policies")
        
        # Process each policy
        all_chunks = []
        for policy in policies:
            logger.info(f"Processing policy: {policy['doc_title']}")
            chunks = chunk_policy_sections(policy)
            
            # Generate embeddings for each chunk
            for chunk in chunks:
                logger.info(f"  Generating embedding for section: {chunk['section']}")
                embedding = embedding_service.generate_embedding(chunk["text"])
                chunk["embedding"] = embedding
            
            all_chunks.extend(chunks)
        
        # Insert all chunks into Milvus
        logger.info(f"Inserting {len(all_chunks)} chunks into Milvus...")
        milvus_service.insert_policy_chunks(all_chunks)
        logger.info("✓ Successfully inserted all chunks")
        
        # Verify insertion
        logger.info("\nVerifying insertion with a test query...")
        test_query = "What are the transaction reporting thresholds?"
        test_embedding = embedding_service.generate_embedding(test_query)
        results = milvus_service.search_similar_policies(test_embedding, top_k=3)
        
        logger.info(f"\nTest query: '{test_query}'")
        logger.info(f"Retrieved {len(results)} results:")
        for i, result in enumerate(results, 1):
            logger.info(f"\n{i}. {result['doc_title']}")
            logger.info(f"   Section: {result['section']}")
            logger.info(f"   Relevance: {result['relevance_score']:.3f}")
            logger.info(f"   Text preview: {result['text'][:150]}...")
        
        logger.info("\n✅ Milvus initialization completed successfully!")
        logger.info(f"Total chunks inserted: {len(all_chunks)}")
        logger.info(f"Total policies: {len(policies)}")
        logger.info("\nYou can now start the backend server and it will connect to Milvus.")
        
    except Exception as e:
        logger.error(f"❌ Error during initialization: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        milvus_service.disconnect()
    
    return True


if __name__ == "__main__":
    success = initialize_milvus()
    sys.exit(0 if success else 1)
