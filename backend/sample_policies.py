"""
Sample AML/KYC policies for demo purposes
"""

SAMPLE_POLICIES = [
    {
        "title": "AML Transaction Monitoring - Large Cash Transactions",
        "content": """
Section 1: Large Cash Transaction Reporting

1.1 Threshold Requirements
All cash transactions exceeding USD 10,000 (or equivalent in local currency) must be reported within 24 hours to the Financial Intelligence Unit (FIU).

1.2 Suspicious Activity Indicators
- Multiple transactions just below the reporting threshold (structuring)
- Unusual patterns of cash deposits inconsistent with customer profile
- Cash transactions with no apparent business or lawful purpose
- Customer reluctance to provide information or documentation

1.3 Enhanced Due Diligence
For transactions exceeding USD 50,000:
- Verify source of funds with supporting documentation
- Obtain senior management approval
- Conduct additional background checks on all parties
- Monitor subsequent account activity for 90 days

1.4 Record Retention
All records related to large cash transactions must be retained for a minimum of 7 years.
        """,
        "source": "internal",
        "topic": "aml",
        "version": "2.1",
    },
    {
        "title": "KYC Customer Identification and Verification",
        "content": """
Section 1: Customer Identification Program

1.1 Individual Customers
Collect and verify the following:
- Full legal name
- Date of birth
- Residential address (verified through utility bill or bank statement)
- Government-issued identification (passport, driver's license, national ID)
- Tax identification number

1.2 Business Entities
For corporate customers, obtain:
- Certificate of incorporation or business registration
- Articles of association
- List of beneficial owners (25% or greater ownership)
- Board resolution authorizing account opening
- Source of funds and purpose of business relationship

1.3 Politically Exposed Persons (PEPs)
Enhanced screening required for:
- Current and former senior government officials
- Immediate family members of PEPs
- Close associates of PEPs
Apply enhanced due diligence including senior management approval and ongoing monitoring.

1.4 Verification Methods
- In-person verification preferred
- Video verification acceptable with liveness detection
- Third-party verification from approved vendors
- Biometric verification where available
        """,
        "source": "internal",
        "topic": "kyc",
        "version": "3.0",
    },
    {
        "title": "OFAC Sanctions Screening Requirements",
        "content": """
Section 1: Sanctions Screening Protocol

1.1 Screening Obligations
All transactions must be screened against:
- OFAC Specially Designated Nationals (SDN) List
- OFAC Consolidated Sanctions List
- UN Security Council Sanctions Lists
- EU Sanctions Lists
- Local regulatory sanctions lists

1.2 Screening Triggers
Perform sanctions screening:
- At customer onboarding
- Before processing each transaction
- Daily batch screening of existing customers
- When sanctions lists are updated

1.3 Match Resolution
For potential matches:
- Immediate transaction hold
- Manual review by compliance officer within 2 hours
- Compare all available identifying information
- Document decision-making process
- Escalate uncertain matches to senior management

1.4 Prohibited Countries
Transactions involving the following countries are strictly prohibited:
- North Korea
- Iran (except authorized humanitarian transactions)
- Syria
- Crimea region of Ukraine

1.5 Blocked Assets
If assets are identified as blocked:
- Immediately freeze the assets
- File a blocking report within 10 business days
- Do not notify the customer prior to filing
- Maintain strict confidentiality
        """,
        "source": "ofac",
        "topic": "sanctions",
        "version": "4.2",
    },
    {
        "title": "High-Risk Country Monitoring",
        "content": """
Section 1: Geographic Risk Assessment

1.1 High-Risk Jurisdictions
Countries identified by FATF as having strategic AML/CFT deficiencies require enhanced due diligence:
- Democratic People's Republic of Korea (DPRK)
- Iran
- Myanmar

1.2 Enhanced Due Diligence Measures
For transactions involving high-risk countries:
- Obtain additional documentation on source of funds
- Verify the purpose and nature of the transaction
- Require senior management approval for amounts exceeding USD 5,000
- Conduct enhanced ongoing monitoring
- Review customer relationship every 6 months

1.3 Monitoring Requirements
- Real-time transaction monitoring for sanctioned countries
- Daily review of transactions to/from high-risk jurisdictions
- Automated alerts for patterns involving multiple high-risk countries
- Quarterly risk assessment of customer base by country

1.4 Correspondent Banking
Additional controls for correspondent banking relationships:
- Annual on-site visits or third-party audits
- Certification of AML program compliance
- Screening of correspondent bank's customer base
        """,
        "source": "fatf",
        "topic": "aml",
        "version": "2.0",
    },
    {
        "title": "Fraud Detection and Prevention",
        "content": """
Section 1: Transaction Fraud Indicators

1.1 Red Flags for Fraudulent Activity
- Transactions inconsistent with customer profile or business
- Unusual wire transfer activity, especially to foreign countries
- Multiple small transactions to the same beneficiary
- Customer requests for urgency without valid explanation
- Reluctance to provide information about transaction purpose
- Use of multiple accounts for no apparent reason

1.2 Identity Theft Indicators
- Recent change of address followed by large transactions
- Multiple failed authentication attempts
- Requests to change contact information to unfamiliar locations
- Suspicious identity documents or information discrepancies

1.3 Business Email Compromise (BEC)
Warning signs:
- Last-minute changes to payment instructions
- Requests for wire transfers to new beneficiaries
- Communication from executives outside normal channels
- Urgent requests bypassing normal approval processes

1.4 Response Protocol
Upon detecting potential fraud:
- Immediately place transaction on hold
- Contact customer using verified contact information
- Document all communications
- File Suspicious Activity Report (SAR) if warranted
- Notify law enforcement if fraud confirmed

1.5 Customer Education
- Provide fraud awareness training to customers
- Alert customers to common fraud schemes
- Encourage reporting of suspicious communications
- Implement transaction confirmation protocols
        """,
        "source": "internal",
        "topic": "fraud",
        "version": "1.5",
    },
    {
        "title": "RBI Guidelines on Risk-Based KYC",
        "content": """
Section 1: Risk Categorization of Customers

1.1 Customer Risk Categories
Classify customers into three risk categories:

Low Risk:
- Salaried employees with reputable employers
- Government departments and organizations
- Domestic transactions only
- Simple product usage

Medium Risk:
- Self-employed individuals
- Small businesses and partnerships
- Limited international transactions
- Multiple product relationships

High Risk:
- Non-resident customers
- High net worth individuals
- Politically exposed persons (PEPs)
- Customers from high-risk countries
- Complex business structures
- Significant cash transactions

1.2 Periodic Review Requirements
- Low Risk: Every 10 years
- Medium Risk: Every 8 years
- High Risk: Every 2 years or more frequently

1.3 Enhanced Due Diligence for High-Risk Customers
- Obtain information on source of wealth and source of funds
- Seek senior management approval for establishing relationship
- Conduct enhanced monitoring of transactions
- Implement additional controls as deemed necessary

1.4 Simplified Due Diligence
Permitted for low-risk customers:
- Government departments
- Persons residing in designated low-risk areas
- Accounts with balances below specified thresholds
        """,
        "source": "rbi",
        "topic": "kyc",
        "version": "5.0",
    }
]


def get_sample_policies():
    """Return list of sample policies"""
    return SAMPLE_POLICIES
