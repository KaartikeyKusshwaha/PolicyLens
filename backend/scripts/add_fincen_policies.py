"""
Add real AML policies from FinCEN Bank Secrecy Act and update Milvus
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


def get_fincen_bsa_policies():
    """Real AML policies based on FinCEN Bank Secrecy Act"""
    return [
        {
            "doc_id": "POL-BSA-CTR-001",
            "doc_title": "FinCEN Currency Transaction Report (CTR) Requirements",
            "version": "3.0",
            "source": "fincen",
            "topic": "aml",
            "sections": [
                {
                    "section": "CTR Filing Requirements - 31 USC 5313",
                    "text": "Financial institutions must file a Currency Transaction Report (CTR) for each transaction in currency of more than $10,000. This includes deposits, withdrawals, exchanges of currency, or other payments or transfers. Multiple transactions must be aggregated if they total more than $10,000 in one business day. CTRs must be filed within 15 calendar days following the day the reportable transaction occurs. Exemptions exist for certain established customers, but these must be documented and renewed annually."
                },
                {
                    "section": "Structuring and Evasion - 31 USC 5324",
                    "text": "No person shall, for the purpose of evading reporting requirements, cause or attempt to cause a financial institution to fail to file a required CTR, cause a financial institution to file a CTR that contains a material omission or misstatement of fact, or structure or assist in structuring any transaction with one or more financial institutions. Structuring is a federal crime punishable by up to 5 years imprisonment and a fine of $250,000. Financial institutions must monitor for and report patterns of transactions that appear designed to evade the $10,000 threshold."
                },
                {
                    "section": "CTR Exemption Criteria and Monitoring",
                    "text": "Eligible non-listed businesses and payroll customers may be exempt from CTR filing after 12 months of account history and documented verification. Banks must conduct annual reviews of all exemptions. If a financial institution learns that an exempt customer no longer meets eligibility criteria, exemption must be revoked within 30 days. Suspicious activity involving an exempt customer must always be reported via SAR regardless of exemption status. Phase I exemptions apply to banks, government agencies, and listed public companies. Phase II exemptions cover non-listed businesses meeting specific criteria."
                }
            ]
        },
        {
            "doc_id": "POL-BSA-SAR-001",
            "doc_title": "FinCEN Suspicious Activity Report (SAR) Requirements",
            "version": "4.2",
            "source": "fincen",
            "topic": "aml",
            "sections": [
                {
                    "section": "SAR Filing Obligations - 31 CFR 1020.320",
                    "text": "Financial institutions must file a SAR for any transaction conducted or attempted involving $5,000 or more where the institution knows, suspects, or has reason to suspect: (1) the transaction involves funds derived from illegal activity or is intended to hide or disguise such funds; (2) the transaction is designed to evade Bank Secrecy Act requirements; (3) the transaction has no business or apparent lawful purpose and the institution knows of no reasonable explanation after examining available facts; or (4) the transaction involves use of the institution to facilitate criminal activity. SARs must be filed within 30 calendar days of initial detection."
                },
                {
                    "section": "Red Flags and Suspicious Activity Indicators",
                    "text": "Indicators requiring SAR consideration include: customer reluctance to provide complete information, attempts to avoid reporting thresholds through structuring, unexplained wire transfer activity to high-risk jurisdictions, transactions inconsistent with customer's business, rapid movement of funds through accounts, use of multiple accounts or locations without clear purpose, deposits of sequentially numbered monetary instruments, cash deposits followed by immediate wire transfers, customer inquiries suggesting desire to evade reporting, and transactions with parties on OFAC sanctions lists. The $5,000 threshold is an aggregate for the suspicious activity, not each individual transaction."
                },
                {
                    "section": "SAR Confidentiality and Safe Harbor Protections - 31 USC 5318(g)",
                    "text": "A financial institution and its officers, employees, and agents are protected from liability for disclosure of suspicious activity through SAR filing. The filing of a SAR, or any information contained therein, shall not be disclosed to any person involved in the transaction, except as necessary to fulfill the institution's reporting obligations. Violation of SAR confidentiality rules may result in civil penalties up to $100,000 and criminal penalties. The safe harbor provision applies to any disclosure made in a SAR or at the request of FinCEN, federal law enforcement, or federal regulatory agencies. No customer notice is required or permitted when filing a SAR."
                }
            ]
        },
        {
            "doc_id": "POL-BSA-CDD-001",
            "doc_title": "FinCEN Customer Due Diligence (CDD) Final Rule",
            "version": "2.1",
            "source": "fincen",
            "topic": "kyc",
            "sections": [
                {
                    "section": "CDD Four Pillars - 31 CFR 1010.230",
                    "text": "The CDD Rule establishes four core requirements for covered financial institutions: (1) Customer identification and verification under the Customer Identification Program (CIP) requirements; (2) Beneficial ownership identification and verification for legal entity customers; (3) Understanding the nature and purpose of customer relationships to develop customer risk profiles; (4) Conducting ongoing monitoring to identify and report suspicious transactions and, on a risk basis, maintain and update customer information. These requirements apply at account opening and must be updated on a risk-based schedule determined by the institution's AML program."
                },
                {
                    "section": "Beneficial Ownership Requirements - 31 CFR 1010.230(b)",
                    "text": "For legal entity customers (corporations, LLCs, partnerships, trusts), financial institutions must identify and verify the identity of: (1) Each beneficial owner - any individual who owns 25% or more equity interest (ownership prong); and (2) One individual with significant managerial control (control prong). Legal entity customers must provide a Beneficial Ownership Certification Form at account opening. Verification standards may be less stringent than CIP requirements. Exemptions apply to publicly traded companies, banks, government entities, investment companies, and certain other regulated entities. Updated beneficial ownership information must be obtained when the institution becomes aware of changes."
                },
                {
                    "section": "Enhanced Due Diligence for High-Risk Customers",
                    "text": "Financial institutions must implement risk-based enhanced due diligence (EDD) procedures for higher-risk customers. High-risk categories include: foreign correspondent accounts, private banking accounts for non-US persons, politically exposed persons (PEPs), customers from high-risk geographic locations per FATF and FinCEN guidance, businesses with complex ownership structures, cash-intensive businesses, money services businesses, and virtual asset service providers. EDD must include understanding source of wealth and funds, obtaining additional documentation, enhanced transaction monitoring with lower thresholds, more frequent account reviews (at least annually), and senior management approval for establishing and maintaining relationships."
                }
            ]
        },
        {
            "doc_id": "POL-BSA-RECORDKEEPING-001",
            "doc_title": "BSA Recordkeeping and Retention Requirements",
            "version": "2.0",
            "source": "fincen",
            "topic": "aml",
            "sections": [
                {
                    "section": "Five-Year Retention Rule - 31 CFR 1010.430",
                    "text": "Financial institutions must retain records for a minimum of five years from the date of transaction or five years from the date a record is made, whichever is later. Required records include: signature cards and account opening documents, CTRs and supporting documentation, SARs and supporting documentation, all records related to compliance with the Bank Secrecy Act, funds transfer records for domestic and international wires, monetary instrument sales records, and currency exchange records. Records must be retrievable within a reasonable time period and made available to FinCEN and appropriate regulatory agencies upon request. Electronic record retention is permitted if records are easily accessible and can be reproduced."
                },
                {
                    "section": "Funds Transfer Recordkeeping - 31 CFR 1010.410",
                    "text": "For funds transfers of $3,000 or more, financial institutions must obtain and retain specific information. For transmitter's financial institution: sender's name and address if account holder, or verified name and address if non-account holder, sender's account number, amount and execution date, identity of recipient's financial institution, and recipient's name and account number. For recipient's financial institution: must verify recipient identity for non-account holders. For intermediary banks: must retain all information received. The Travel Rule requires this information accompany each transfer. Cross-border transmittals over $3,000 must include additional information such as sender's address and account number."
                },
                {
                    "section": "Monetary Instrument Log and Recordkeeping",
                    "text": "Financial institutions must maintain a monetary instrument log for each cash purchase of monetary instruments (e.g., cashier's checks, money orders, traveler's checks) between $3,000 and $10,000. Records must include: date of transaction, type and serial number of instruments purchased, name and address of purchaser (verification required), if purchaser is not account holder. Multiple purchases by the same person in one day must be aggregated. Institutions selling $1,000 or more in money orders or traveler's checks per transaction must maintain records even below $3,000 threshold. These records must be available for SAR and CTR preparation and regulatory examination."
                }
            ]
        },
        {
            "doc_id": "POL-BSA-INTERNATIONAL-001",
            "doc_title": "FinCEN International AML Requirements and High-Risk Jurisdictions",
            "version": "1.8",
            "source": "fincen",
            "topic": "sanctions",
            "sections": [
                {
                    "section": "High-Risk Jurisdictions - FATF and FinCEN Advisories",
                    "text": "Financial institutions must apply enhanced due diligence to transactions involving jurisdictions identified by FATF as high-risk or non-cooperative. As of current guidance, jurisdictions under increased monitoring include: Myanmar (Burma), Democratic People's Republic of Korea (DPRK/North Korea), Iran, Haiti, Jamaica, Jordan, Mali, Mozambique, Nigeria, Philippines, Senegal, South Sudan, Syria, Tanzania, Turkey, Uganda, United Arab Emirates, Vietnam, and Yemen. Jurisdictions subject to Call for Action (highest risk) require financial institutions to apply counter-measures and enhanced scrutiny. Transactions with these jurisdictions may require additional documentation, senior management approval, and enhanced monitoring regardless of transaction size."
                },
                {
                    "section": "Cross-Border Correspondent Account Requirements - Section 312",
                    "text": "US financial institutions establishing correspondent accounts for foreign financial institutions must: (1) Conduct enhanced due diligence including obtaining ownership information, description of AML program, purpose of account, anticipated activity, and nature of customer base; (2) Assess the foreign bank's AML controls and regulatory environment; (3) Ascertain whether the foreign bank is subject to comprehensive AML supervision; (4) Monitor transactions for suspicious activity; (5) Obtain senior management approval before opening accounts. Correspondent accounts for shell banks (banks with no physical presence in any country) are prohibited. US banks must ensure foreign correspondent banks do not permit shell banks to use their accounts."
                },
                {
                    "section": "FBAR Reporting Requirements - 31 CFR 1010.350",
                    "text": "US persons with financial interest in or signature authority over foreign financial accounts exceeding $10,000 aggregate value at any time during the calendar year must file a Report of Foreign Bank and Financial Accounts (FBAR) electronically with FinCEN. FBAR deadline is April 15 with automatic extension to October 15. Accounts include: bank accounts, brokerage accounts, mutual funds, trusts, and other financial accounts maintained with foreign financial institutions. Willful failure to file FBAR can result in criminal penalties up to $250,000 or 5 years imprisonment. Civil penalties for willful violations can reach the greater of $100,000 or 50% of account balance. Financial institutions must assist customers in understanding FBAR obligations."
                }
            ]
        },
        {
            "doc_id": "POL-BSA-PROGRAM-001",
            "doc_title": "BSA/AML Compliance Program Requirements",
            "version": "3.1",
            "source": "fincen",
            "topic": "aml",
            "sections": [
                {
                    "section": "AML Program Five Pillars - 31 CFR 1020.210",
                    "text": "Every financial institution must establish and maintain an effective AML compliance program that includes at minimum: (1) A system of internal controls to assure ongoing compliance with BSA requirements; (2) Independent testing for compliance conducted by an internal audit department, outside auditors, consultants, or other qualified persons; (3) Designation of an individual or individuals responsible for coordinating and monitoring day-to-day compliance (BSA Officer); (4) Training for appropriate personnel on BSA requirements, internal policies, and procedures; (5) Risk-based procedures for ongoing customer due diligence, including monitoring transactions and maintaining/updating customer information. The program must be approved by the board of directors or equivalent governing body and be commensurate with the institution's size, complexity, and risk profile."
                },
                {
                    "section": "Risk Assessment Requirements - BSA/AML Manual",
                    "text": "Financial institutions must conduct periodic risk assessments considering: customer types and risk profiles, products and services offered (particularly high-risk products like wire transfers, correspondent banking, trade finance, and cash transactions), geographic locations of customers and transactions, and delivery channels (internet banking, ATMs, mobile banking). Risk assessments must identify specific money laundering and terrorist financing risks and be documented. Risk assessment findings drive the design of internal controls, monitoring systems, independent testing scope, training programs, and resource allocation. High-risk areas require enhanced monitoring, additional controls, and more frequent review. Risk assessments must be updated when new products, services, or customer types are introduced."
                },
                {
                    "section": "Training and Awareness Requirements",
                    "text": "AML training must be provided to all appropriate personnel and must be ongoing. Training audience includes: front-line staff with customer contact, back-office operations staff processing transactions, compliance and audit personnel, senior management and board members. Training must cover: institution's BSA/AML policies and procedures, employees' roles in compliance, red flag indicators for suspicious activity, CTR and SAR filing requirements, CDD and beneficial ownership requirements, sanctions screening obligations, and penalties for non-compliance. New employees must receive training within first 90 days. Ongoing training must occur at least annually for all staff. Advanced training required for BSA Officer and compliance staff. Training must be documented with attendance records and testing to ensure comprehension."
                }
            ]
        }
    ]


def chunk_and_add_policies():
    """Add new policies to Milvus"""
    logger.info("Adding FinCEN Bank Secrecy Act policies to Milvus...")
    
    embedding_service = EmbeddingService()
    milvus_service = MilvusService()
    
    try:
        # Connect
        milvus_service.connect()
        logger.info("✓ Connected to Milvus")
        
        # Get new policies
        policies = get_fincen_bsa_policies()
        logger.info(f"Loaded {len(policies)} new FinCEN BSA policies")
        
        # Process each policy
        all_chunks = []
        for policy in policies:
            logger.info(f"\nProcessing: {policy['doc_title']}")
            
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
                
                logger.info(f"  Section: {section['section'][:50]}...")
                embedding = embedding_service.generate_embedding(section["text"])
                chunk["embedding"] = embedding
                all_chunks.append(chunk)
        
        # Insert into Milvus
        logger.info(f"\nInserting {len(all_chunks)} new chunks...")
        milvus_service.insert_policy_chunks(all_chunks)
        logger.info("✓ Successfully inserted all chunks")
        
        # Verify with test queries
        logger.info("\n" + "="*80)
        logger.info("TESTING RETRIEVAL WITH REAL AML QUERIES")
        logger.info("="*80)
        
        test_queries = [
            "What is the threshold for filing a Currency Transaction Report?",
            "When must a Suspicious Activity Report be filed?",
            "What are the beneficial ownership requirements?",
            "What is the record retention period for BSA documents?",
            "Which countries are high-risk for money laundering?"
        ]
        
        for query in test_queries:
            logger.info(f"\nQuery: '{query}'")
            query_embedding = embedding_service.generate_embedding(query)
            results = milvus_service.search_similar_policies(query_embedding, top_k=2)
            
            for i, result in enumerate(results, 1):
                logger.info(f"  [{i}] {result['doc_title']}")
                logger.info(f"      Section: {result['section']}")
                logger.info(f"      Relevance: {result['relevance_score']:.3f}")
                logger.info(f"      Source: {result['source']}")
        
        # Get total count
        from pymilvus import Collection
        collection = Collection("policy_chunks")
        collection.load()
        total = collection.num_entities
        
        logger.info("\n" + "="*80)
        logger.info(f"✅ MILVUS NOW CONTAINS {total} POLICY CHUNKS")
        logger.info(f"   - Original demo policies: 15 chunks")
        logger.info(f"   - New FinCEN BSA policies: {len(all_chunks)} chunks")
        logger.info(f"   - Total in database: {total} chunks")
        logger.info("="*80)
        
        milvus_service.disconnect()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = chunk_and_add_policies()
    sys.exit(0 if success else 1)
