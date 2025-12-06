"""
Load sample AML/FinCEN compliance policies into PolicyLens
"""
import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.document_processor import DocumentProcessor
from services.storage_service import StorageService
from services.embedding_service import EmbeddingService
from services.milvus_service import MilvusService
from models import PolicyDocument, PolicySource, PolicyTopic
from config import settings

# Sample compliance policies
SAMPLE_POLICIES = [
    {
        "title": "FinCEN Customer Due Diligence (CDD) Rule",
        "content": """
# Customer Due Diligence Requirements

## Overview
Financial institutions must implement risk-based Customer Due Diligence (CDD) procedures for all account openings and ongoing monitoring.

## Key Requirements

### 1. Customer Identification
- Collect and verify customer name, date of birth, address, and identification number
- Document must be unexpired government-issued identification
- Maintain records for 5 years after account closure

### 2. Beneficial Ownership
- Identify and verify individuals owning 25% or more of legal entity customers
- Identify one individual with significant control over the entity
- Legal entity customers exclude publicly traded companies and regulated entities

### 3. Customer Risk Profile
- Understand the nature and purpose of customer relationships
- Develop customer risk profiles based on:
  - Type of customer and business
  - Geographic location
  - Expected account activity
  - Source of funds

### 4. Ongoing Monitoring
- Conduct ongoing monitoring to identify and report suspicious transactions
- Update customer information on a risk basis
- Review higher-risk customers more frequently

## Red Flags
- Customer refuses to provide required information
- Customer provides suspicious identification documents
- Unusual transaction patterns inconsistent with business purpose
- Structuring transactions to avoid reporting thresholds
- Rapid movement of funds without clear business purpose

## Compliance Requirements
- Establish written CDD procedures
- Train staff on CDD requirements
- Implement quality assurance reviews
- Report violations to FinCEN
""",
        "source": "FinCEN",
        "category": "Customer Due Diligence",
        "risk_level": "high"
    },
    {
        "title": "Suspicious Activity Reporting (SAR) Requirements",
        "content": """
# Suspicious Activity Reporting Requirements

## Filing Thresholds
Financial institutions must file SARs for transactions involving or aggregating $5,000 or more when:
- The institution knows, suspects, or has reason to suspect the transaction involves funds from illegal activity
- The transaction is designed to evade BSA requirements
- The transaction has no business or lawful purpose
- The transaction involves use of the institution to facilitate criminal activity

## Transaction Red Flags

### Money Laundering Indicators
- Large cash deposits inconsistent with customer business
- Multiple transactions just below reporting thresholds (structuring)
- Wire transfers to/from high-risk jurisdictions
- Transactions with no apparent economic purpose
- Use of multiple accounts to collect and funnel funds
- Rapid movement of funds without clear business purpose

### Terrorist Financing Indicators
- Transactions involving OFAC sanctioned countries or entities
- Charitable organizations with unclear beneficiaries
- Small transactions from multiple sources to single destination
- Transactions with known terrorist locations or individuals

### Structuring Indicators
- Multiple transactions just below $10,000 CTR threshold
- Deposits spread across multiple branches or days
- Customer requests transactions be split
- Multiple individuals making deposits to same account

## Filing Requirements
- File within 30 calendar days of initial detection
- Include complete transaction details and supporting documentation
- Maintain confidentiality - do not notify subject of SAR
- Retain SAR and supporting documentation for 5 years

## Exemptions
- Transactions by government agencies
- Transactions by bank-to-bank transfers
- Transactions by publicly traded companies (with conditions)
""",
        "source": "FinCEN",
        "category": "Suspicious Activity Reporting",
        "risk_level": "critical"
    },
    {
        "title": "High-Risk Jurisdiction Guidelines",
        "content": """
# High-Risk and Non-Cooperative Jurisdictions

## FATF High-Risk Jurisdictions
Transactions involving the following jurisdictions require enhanced due diligence:
- Democratic People's Republic of Korea (DPRK)
- Iran
- Myanmar

## FATF Monitored Jurisdictions (Grey List)
Enhanced monitoring required for jurisdictions with strategic AML/CFT deficiencies:
- Bulgaria
- Burkina Faso
- Cameroon
- Croatia
- Democratic Republic of Congo
- Haiti
- Jamaica
- Mali
- Monaco
- Mozambique
- Nigeria
- Philippines
- Senegal
- South Africa
- South Sudan
- Syria
- Tanzania
- Turkey
- Uganda
- United Arab Emirates
- Vietnam
- Yemen

## Enhanced Due Diligence Requirements
For transactions involving high-risk jurisdictions:
- Verify source of funds and wealth
- Obtain senior management approval
- Conduct enhanced ongoing monitoring
- Increase transaction review frequency
- Document business rationale for relationship
- Consider filing SAR if suspicious indicators present

## Prohibited Transactions
- Direct transactions with DPRK or Iran (unless specifically licensed)
- Transactions with SDN list entities
- Transactions facilitating sanctions evasion
- Correspondent banking for shell banks

## Risk Mitigation
- Implement automated screening for high-risk jurisdictions
- Enhanced training for staff on geographic risks
- Regular review of FATF and OFAC lists
- Document risk assessment for all high-risk relationships
""",
        "source": "FATF/OFAC",
        "category": "Geographic Risk",
        "risk_level": "critical"
    },
    {
        "title": "Wire Transfer Recordkeeping Requirements",
        "content": """
# Wire Transfer and Funds Transfer Recordkeeping

## Travel Rule Requirements
Transmittal orders of $3,000 or more must include:
- Sender's name and address
- Sender's account number or unique identifier
- Sender's financial institution information
- Receiver's name and address
- Receiver's account number or unique identifier
- Receiver's financial institution information
- Date and amount of transaction

## Cross-Border Transfers
International wire transfers require additional information:
- Purpose of payment
- Relationship between sender and receiver
- Source of funds
- Enhanced due diligence for high-risk countries

## Recordkeeping Requirements
- Maintain records for 5 years from date of transaction
- Include complete transaction chain
- Document verification procedures
- Retain supporting documentation

## Red Flags for Wire Transfers
- Wire transfers to/from high-risk jurisdictions
- Multiple small wire transfers to same beneficiary
- Immediate wire transfer of deposited funds
- Wire transfers with no clear business purpose
- Inconsistencies between stated purpose and customer profile
- Frequent changes to beneficiary information
- Use of multiple intermediary banks unnecessarily

## Sanctions Screening
- Screen all parties against OFAC SDN list
- Check for blocked or sanctioned jurisdictions
- Verify no sanctions evasion indicators
- Document screening results

## Reporting Requirements
- File CTR for currency transactions over $10,000
- File SAR for suspicious wire activity
- Report OFAC matches immediately
- Maintain suspicious activity logs
""",
        "source": "FinCEN BSA",
        "category": "Wire Transfers",
        "risk_level": "high"
    },
    {
        "title": "Currency Transaction Reporting (CTR)",
        "content": """
# Currency Transaction Report Requirements

## Filing Threshold
File CTR for each transaction in currency of more than $10,000 conducted by, through, or to a financial institution.

## Multiple Transactions
File CTR for multiple currency transactions that aggregate to more than $10,000 in a single business day by or on behalf of the same person.

## Required Information
- Part I: Person(s) Involved in Transaction
  - Name, address, date of birth
  - Identification type and number
  - Occupation or type of business
  - Account number(s)

- Part II: Amount and Type of Transaction
  - Total cash in
  - Total cash out
  - Type of transaction (deposit, withdrawal, exchange, etc.)

- Part III: Financial Institution Information
  - Name and address
  - TIN/EIN
  - Account number(s) affected

## Filing Deadline
File CTR within 15 calendar days following the day the reportable transaction occurs.

## Exemptions
May exempt certain customers from CTR filing:
- Government agencies
- Listed public companies
- Subsidiaries of listed companies
- Payroll customers (under certain conditions)
- Non-listed businesses (after proper due diligence)

## Exemption Requirements
- Document eligibility verification
- Renew exemptions every two years
- Monitor for suspicious activity (still file SARs)
- Maintain exemption records for 5 years

## Structuring Detection
Monitor for attempts to evade CTR reporting:
- Multiple deposits just under $10,000
- Transactions split across days or branches
- Use of multiple individuals for single customer
- Customer requests to structure transactions

## Penalties
- Civil penalties up to $25,000 per violation
- Criminal penalties for willful violations
- Pattern of negligence can result in bank penalties
""",
        "source": "FinCEN Form 112",
        "category": "Currency Reporting",
        "risk_level": "high"
    },
    {
        "title": "OFAC Sanctions Compliance",
        "content": """
# Office of Foreign Assets Control (OFAC) Compliance

## Sanctions Programs Overview
OFAC administers economic and trade sanctions based on:
- Foreign policy objectives
- National security goals
- Specific threat areas

## Specially Designated Nationals (SDN) List
The SDN list includes:
- Individuals and entities owned/controlled by targeted countries
- Individuals and entities involved in terrorism, narcotics trafficking
- Other threats to national security

## Screening Requirements
Financial institutions must:
- Screen all transactions against SDN list
- Screen account openings and beneficial owners
- Screen wire transfer parties (originator, beneficiary, intermediaries)
- Implement automated screening systems
- Document screening procedures and results

## Prohibited Transactions
- No U.S. person may conduct transactions with SDN list parties
- No transactions involving blocked property
- No facilitation of prohibited transactions by foreign subsidiaries
- No evasion of sanctions through third parties

## Blocking Requirements
When OFAC match identified:
1. Block/reject the transaction immediately
2. Notify OFAC within 10 business days
3. File annual report on blocked property
4. Maintain blocked property until authorized release
5. Do not notify customer until OFAC authorizes

## 50% Rule
Entities owned 50% or more by SDN list parties are also blocked, even if not on SDN list.

## Due Diligence for High-Risk Transactions
- Verify all parties to transaction
- Check for false positives carefully
- Document matching and clearing procedures
- Escalate unclear matches to compliance
- Obtain senior management approval for risks

## Geographic Risk Areas
Enhanced scrutiny for:
- Iran
- North Korea  
- Syria
- Cuba
- Ukraine-related sanctions
- Counter-terrorism sanctions

## Penalties for Violations
- Civil penalties: Greater of $250,000 or twice transaction amount
- Criminal penalties: Up to $1 million and 20 years imprisonment
- Reputational damage and regulatory sanctions
""",
        "source": "OFAC",
        "category": "Sanctions Compliance",
        "risk_level": "critical"
    },
    {
        "title": "Enhanced Due Diligence for High-Risk Customers",
        "content": """
# Enhanced Due Diligence Requirements

## When Required
Enhanced Due Diligence (EDD) required for:
- Politically Exposed Persons (PEPs)
- High-risk geographic locations
- High-risk customer types or businesses
- Unusual or complex ownership structures
- Customers with negative news or adverse media
- Large cash-intensive businesses
- Non-face-to-face customers

## Politically Exposed Persons (PEPs)
PEPs include:
- Senior foreign political figures
- Immediate family members of political figures
- Close associates of political figures
- Senior officials in international organizations

### PEP Due Diligence Requirements
- Senior management approval for onboarding
- Source of wealth verification
- Source of funds verification
- Enhanced ongoing monitoring
- Regular review of relationship (at least annually)
- Screen for adverse media and corruption indicators

## High-Risk Business Types
Enhanced scrutiny for:
- Money services businesses (MSBs)
- Cash-intensive businesses (ATMs, casinos, retail)
- Import/export businesses
- Non-profit organizations
- Virtual asset service providers
- Precious metals/stones dealers
- Real estate brokers and agents

## Enhanced Monitoring Requirements
- More frequent transaction reviews
- Lower thresholds for SAR investigation
- Management information system (MIS) reports
- Regular risk rating updates
- Periodic relationship reviews
- Enhanced transaction screening

## Documentation Requirements
- Detailed customer risk assessment
- Source of funds documentation
- Source of wealth documentation
- Purpose of account and expected activity
- Explanation of unusual transactions
- Management approval and review records

## Red Flags Requiring Additional EDD
- Customer reluctant to provide information
- Complex ownership structure with no clear purpose
- Transactions inconsistent with stated business
- Source of funds unclear or suspicious
- Multiple jurisdictions without business rationale
- Negative news or adverse media hits
- Links to high-risk jurisdictions or entities

## Ongoing Monitoring
- Transaction monitoring with lower thresholds
- Regular risk rating reviews (at least annually)
- Proactive adverse media screening
- Update customer information regularly
- Document all unusual activity
- Consider relationship termination if risks too high
""",
        "source": "FinCEN/FATF",
        "category": "Enhanced Due Diligence",
        "risk_level": "high"
    }
]


async def main():
    """Load all sample policies"""
    print("🔧 Initializing services...")
    
    # Initialize services with config
    milvus_service = MilvusService(host=settings.milvus_host, port=settings.milvus_port)
    milvus_service.connect()  # Connect to Milvus
    embedding_service = EmbeddingService()
    storage_service = StorageService()
    doc_processor = DocumentProcessor(embedding_service, milvus_service)
    
    print(f"📚 Loading {len(SAMPLE_POLICIES)} sample compliance policies...\n")
    
    loaded_count = 0
    for i, policy in enumerate(SAMPLE_POLICIES, 1):
        try:
            print(f"[{i}/{len(SAMPLE_POLICIES)}] Loading: {policy['title']}")
            print(f"   Category: {policy['category']} | Risk Level: {policy['risk_level']}")
            
            # Map category to PolicyTopic
            topic_map = {
                'Customer Due Diligence': PolicyTopic.KYC,
                'Suspicious Activity Reporting': PolicyTopic.AML,
                'Geographic Risk': PolicyTopic.SANCTIONS,
                'Wire Transfers': PolicyTopic.AML,
                'Currency Reporting': PolicyTopic.AML,
                'Sanctions Compliance': PolicyTopic.SANCTIONS,
                'Enhanced Due Diligence': PolicyTopic.KYC
            }
            
            # Map source to PolicySource
            source_map = {
                'FinCEN': PolicySource.INTERNAL,
                'FATF/OFAC': PolicySource.OFAC,
                'FinCEN BSA': PolicySource.INTERNAL,
                'FinCEN Form 112': PolicySource.INTERNAL,
                'OFAC': PolicySource.OFAC,
                'FinCEN/FATF': PolicySource.FATF
            }
            
            # Create PolicyDocument object
            policy_doc = PolicyDocument(
                doc_id=str(uuid.uuid4()),
                title=policy['title'],
                content=policy['content'],
                source=source_map.get(policy['source'], PolicySource.INTERNAL),
                topic=topic_map.get(policy['category'], PolicyTopic.GENERAL),
                metadata={
                    'category': policy['category'],
                    'risk_level': policy['risk_level'],
                    'original_source': policy['source']
                }
            )
            
            # Process policy document
            chunks = doc_processor.process_document(policy_doc)
            
            print(f"   ✅ Loaded: {len(chunks)} chunks processed")
            loaded_count += 1
                
        except Exception as e:
            print(f"   ❌ Error loading policy: {str(e)}")
            import traceback
            traceback.print_exc()
        
        print()
    
    print(f"\n{'='*60}")
    print(f"✅ Successfully loaded {loaded_count}/{len(SAMPLE_POLICIES)} policies")
    print(f"{'='*60}\n")
    
    # Display summary
    print("📊 Policy Summary:")
    print(f"   • Customer Due Diligence (CDD)")
    print(f"   • Suspicious Activity Reporting (SAR)")
    print(f"   • High-Risk Jurisdictions")
    print(f"   • Wire Transfer Requirements")
    print(f"   • Currency Transaction Reporting (CTR)")
    print(f"   • OFAC Sanctions Compliance")
    print(f"   • Enhanced Due Diligence (EDD)")
    print()
    print("🚀 Your PolicyLens system is now ready for transaction evaluation!")
    print("   Try evaluating a transaction at: http://localhost:3000/evaluate")


if __name__ == "__main__":
    asyncio.run(main())
