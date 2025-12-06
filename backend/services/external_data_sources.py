"""
External Data Sources Integration
Connects to OFAC, FATF, RBI and other compliance data sources
"""

import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime
import csv
import io
import json
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class OFACConnector:
    """
    Connector for OFAC Sanctions Lists
    https://www.treasury.gov/ofac/downloads/
    """
    
    BASE_URL = "https://www.treasury.gov/ofac/downloads"
    
    # OFAC SDN (Specially Designated Nationals) list
    SDN_XML_URL = f"{BASE_URL}/sdn.xml"
    SDN_CSV_URL = f"{BASE_URL}/sdn.csv"
    
    # Consolidated sanctions list
    CONSOLIDATED_URL = f"{BASE_URL}/consolidated/consolidated.xml"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PolicyLens-Compliance-System/1.0'
        })
    
    def fetch_sdn_list(self, format: str = 'csv') -> Dict:
        """
        Fetch OFAC Specially Designated Nationals list
        
        Args:
            format: 'csv' or 'xml'
            
        Returns:
            Dict with sanctions data and metadata
        """
        try:
            url = self.SDN_CSV_URL if format == 'csv' else self.SDN_XML_URL
            logger.info(f"Fetching OFAC SDN list from {url}")
            
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            if format == 'csv':
                return self._parse_sdn_csv(response.text)
            else:
                return self._parse_sdn_xml(response.text)
                
        except Exception as e:
            logger.error(f"Error fetching OFAC SDN list: {e}")
            raise
    
    def _parse_sdn_csv(self, csv_content: str) -> Dict:
        """Parse OFAC SDN CSV format - limit to 50 most important entries for performance"""
        sanctions = []
        
        # Priority programs for importance sorting
        priority_programs = ['SDGT', 'SDNTK', 'IRAN', 'SYRIA', 'CUBA', 'UKRAINE-EO13662', 'RUSSIA']
        
        csv_reader = csv.DictReader(io.StringIO(csv_content))
        priority_entries = []
        other_entries = []
        total_count = 0
        
        # Fast collection of priority entries and first 200 others
        for row in csv_reader:
            total_count += 1
            program = row.get('Program', '')
            
            entry = {
                'entity_number': row.get('ent_num', ''),
                'name': row.get('SDN_Name', ''),
                'type': row.get('SDN_Type', ''),
                'program': program,
                'title': row.get('Title', ''),
                'call_sign': row.get('Call_Sign', ''),
                'vessel_type': row.get('Vess_type', ''),
                'tonnage': row.get('Tonnage', ''),
                'grt': row.get('GRT', ''),
                'vessel_flag': row.get('Vess_flag', ''),
                'vessel_owner': row.get('Vess_owner', ''),
                'remarks': row.get('Remarks', '')
            }
            
            # Prioritize important programs
            if program in priority_programs:
                priority_entries.append(entry)
            elif len(other_entries) < 200:  # Only keep first 200 non-priority
                other_entries.append(entry)
            
            # Early exit after collecting enough priority entries
            if len(priority_entries) >= 50:
                break
        
        # Combine and limit to 50
        sanctions = (priority_entries + other_entries)[:50]
        
        return {
            'source': 'OFAC_SDN',
            'fetched_at': datetime.utcnow().isoformat(),
            'count': len(sanctions),
            'total_available': total_count,
            'data': sanctions
        }
    
    def _parse_sdn_xml(self, xml_content: str) -> Dict:
        """Parse OFAC SDN XML format"""
        # Simplified XML parsing - can be enhanced with xmltodict
        soup = BeautifulSoup(xml_content, 'xml')
        sanctions = []
        
        for entry in soup.find_all('sdnEntry'):
            sanctions.append({
                'uid': entry.find('uid').text if entry.find('uid') else '',
                'name': entry.find('firstName').text if entry.find('firstName') else '' + 
                        ' ' + (entry.find('lastName').text if entry.find('lastName') else ''),
                'type': entry.find('sdnType').text if entry.find('sdnType') else '',
                'programs': [p.text for p in entry.find_all('program')],
                'remarks': entry.find('remarks').text if entry.find('remarks') else ''
            })
        
        return {
            'source': 'OFAC_SDN',
            'fetched_at': datetime.utcnow().isoformat(),
            'count': len(sanctions),
            'data': sanctions
        }
    
    def fetch_consolidated_list(self) -> Dict:
        """Fetch OFAC consolidated sanctions list"""
        try:
            logger.info("Fetching OFAC consolidated sanctions list")
            response = self.session.get(self.CONSOLIDATED_URL, timeout=30)
            response.raise_for_status()
            
            return self._parse_consolidated_xml(response.text)
            
        except Exception as e:
            logger.error(f"Error fetching OFAC consolidated list: {e}")
            raise
    
    def _parse_consolidated_xml(self, xml_content: str) -> Dict:
        """Parse consolidated sanctions XML"""
        soup = BeautifulSoup(xml_content, 'xml')
        sanctions = []
        
        for entry in soup.find_all('sdnEntry'):
            sanctions.append({
                'uid': entry.find('uid').text if entry.find('uid') else '',
                'name': entry.get_text(strip=True),
                'source': 'OFAC_CONSOLIDATED'
            })
        
        return {
            'source': 'OFAC_CONSOLIDATED',
            'fetched_at': datetime.utcnow().isoformat(),
            'count': len(sanctions),
            'data': sanctions
        }


class FATFConnector:
    """
    Connector for FATF High-Risk and Monitored Jurisdictions
    https://www.fatf-gafi.org/
    """
    
    BASE_URL = "https://www.fatf-gafi.org"
    HIGH_RISK_URL = f"{BASE_URL}/en/publications/high-risk-and-other-monitored-jurisdictions"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PolicyLens-Compliance-System/1.0'
        })
        
        # Manually maintained list (updated from FATF website)
        # As of December 2024
        self.high_risk_countries = [
            "Democratic People's Republic of Korea (DPRK)",
            "Iran",
            "Myanmar"
        ]
        
        self.monitored_countries = [
            "Albania", "Barbados", "Burkina Faso", "Cambodia",
            "Cayman Islands", "Democratic Republic of Congo",
            "Gibraltar", "Haiti", "Jamaica", "Jordan",
            "Mali", "Morocco", "Mozambique", "Nigeria",
            "Panama", "Philippines", "Senegal", "South Africa",
            "South Sudan", "Syria", "Tanzania", "Türkiye",
            "Uganda", "United Arab Emirates", "Vietnam", "Yemen"
        ]
    
    def fetch_high_risk_jurisdictions(self) -> Dict:
        """
        Fetch FATF high-risk jurisdictions
        Note: FATF doesn't provide an API, so we use a maintained list
        """
        return {
            'source': 'FATF_HIGH_RISK',
            'fetched_at': datetime.utcnow().isoformat(),
            'last_manual_update': '2024-12-01',
            'count': len(self.high_risk_countries),
            'data': [
                {
                    'country': country,
                    'risk_level': 'HIGH',
                    'status': 'Call for Action',
                    'description': 'Jurisdiction under FATF Call for Action'
                }
                for country in self.high_risk_countries
            ]
        }
    
    def fetch_monitored_jurisdictions(self) -> Dict:
        """Fetch FATF monitored jurisdictions (increased monitoring)"""
        return {
            'source': 'FATF_MONITORED',
            'fetched_at': datetime.utcnow().isoformat(),
            'last_manual_update': '2024-12-01',
            'count': len(self.monitored_countries),
            'data': [
                {
                    'country': country,
                    'risk_level': 'MEDIUM',
                    'status': 'Increased Monitoring',
                    'description': 'Jurisdiction under increased monitoring'
                }
                for country in self.monitored_countries
            ]
        }
    
    def scrape_latest_updates(self) -> Dict:
        """
        Scrape FATF website for latest updates
        Returns the most recent publication data
        """
        try:
            logger.info("Scraping FATF website for updates")
            response = self.session.get(self.HIGH_RISK_URL, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract publication date and content
            updates = {
                'source': 'FATF_WEBSITE',
                'fetched_at': datetime.utcnow().isoformat(),
                'url': self.HIGH_RISK_URL,
                'content': soup.get_text()[:5000],  # First 5000 chars
                'note': 'Scraped content - manual review recommended'
            }
            
            return updates
            
        except Exception as e:
            logger.error(f"Error scraping FATF website: {e}")
            # Return cached data instead
            return {
                'source': 'FATF_CACHED',
                'error': str(e),
                'high_risk': self.fetch_high_risk_jurisdictions(),
                'monitored': self.fetch_monitored_jurisdictions()
            }


class RBIConnector:
    """
    Connector for Reserve Bank of India Circulars
    https://www.rbi.org.in/
    """
    
    BASE_URL = "https://www.rbi.org.in"
    CIRCULARS_URL = f"{BASE_URL}/Scripts/BS_ViewMasCirculardetails.aspx"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PolicyLens-Compliance-System/1.0'
        })
    
    def fetch_recent_circulars(self, category: str = "AML", limit: int = 50) -> Dict:
        """
        Fetch recent RBI circulars
        
        Args:
            category: AML, KYC, Banking, etc.
            limit: Number of recent circulars to fetch
        """
        try:
            logger.info(f"Fetching RBI circulars for category: {category}")
            
            # RBI circular search parameters
            params = {
                'Id': category,
                'Mode': 'All'
            }
            
            response = self.session.get(self.CIRCULARS_URL, params=params, timeout=30)
            response.raise_for_status()
            
            return self._parse_circulars_page(response.text, category, limit)
            
        except Exception as e:
            logger.error(f"Error fetching RBI circulars: {e}")
            raise
    
    def _parse_circulars_page(self, html_content: str, category: str, limit: int) -> Dict:
        """Parse RBI circulars HTML page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        circulars = []
        
        # Find circular entries in the page
        # Note: RBI website structure may change, this is a basic scraper
        tables = soup.find_all('table')
        
        for table in tables[:limit]:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    circular = {
                        'date': cols[0].get_text(strip=True) if len(cols) > 0 else '',
                        'title': cols[1].get_text(strip=True) if len(cols) > 1 else '',
                        'circular_no': cols[2].get_text(strip=True) if len(cols) > 2 else '',
                        'category': category,
                        'url': ''
                    }
                    
                    # Extract URL if available
                    link = cols[1].find('a') if len(cols) > 1 else None
                    if link and link.get('href'):
                        circular['url'] = self.BASE_URL + link.get('href')
                    
                    if circular['title']:  # Only add if has content
                        circulars.append(circular)
        
        return {
            'source': 'RBI_CIRCULARS',
            'category': category,
            'fetched_at': datetime.utcnow().isoformat(),
            'count': len(circulars),
            'data': circulars[:limit]
        }
    
    def download_circular_pdf(self, url: str) -> bytes:
        """Download a specific RBI circular PDF"""
        try:
            logger.info(f"Downloading RBI circular from {url}")
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Error downloading RBI circular: {e}")
            raise


class ExternalDataManager:
    """
    Manager for all external data sources
    Orchestrates fetching, processing, and storing external compliance data
    """
    
    def __init__(self, document_processor=None, storage_service=None):
        self.ofac = OFACConnector()
        self.fatf = FATFConnector()
        self.rbi = RBIConnector()
        self.document_processor = document_processor
        self.storage_service = storage_service
        self.logger = logging.getLogger(__name__)
    
    async def fetch_data(self, source: str) -> Dict:
        """Fetch data from a specific source"""
        source = source.upper()
        result = {
            'source': source,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'success',
            'data': None,
            'error': None
        }
        
        try:
            if source == 'OFAC':
                data = self.ofac.fetch_sdn_list()
                result['data'] = data
                result['records_count'] = data.get('count', 0)
                self.logger.info(f"✓ Fetched {result['records_count']} OFAC SDN entries")
                
                # Store fetch history
                if self.storage_service:
                    self.storage_service.store_external_data_fetch(
                        source='OFAC',
                        status='success',
                        records_fetched=result['records_count'],
                        message=f"Successfully fetched {result['records_count']} SDN entries"
                    )
                    
            elif source == 'FATF':
                high_risk = self.fatf.fetch_high_risk_jurisdictions()
                monitored = self.fatf.fetch_monitored_jurisdictions()
                result['data'] = {
                    'high_risk': high_risk,
                    'monitored': monitored
                }
                result['records_count'] = high_risk.get('count', 0) + monitored.get('count', 0)
                self.logger.info(f"✓ Fetched FATF risk jurisdictions")
                
                # Store fetch history
                if self.storage_service:
                    self.storage_service.store_external_data_fetch(
                        source='FATF',
                        status='success',
                        records_fetched=result['records_count'],
                        message=f"Successfully fetched risk jurisdictions"
                    )
                    
            elif source == 'RBI':
                data = self.rbi.fetch_recent_circulars(category='AML', limit=20)
                result['data'] = data
                result['records_count'] = data.get('count', 0)
                self.logger.info(f"✓ Fetched {result['records_count']} RBI circulars")
                
                # Store fetch history
                if self.storage_service:
                    self.storage_service.store_external_data_fetch(
                        source='RBI',
                        status='success',
                        records_fetched=result['records_count'],
                        message=f"Successfully fetched {result['records_count']} circulars"
                    )
            else:
                result['status'] = 'error'
                result['error'] = f"Unknown source: {source}. Valid sources: OFAC, FATF, RBI"
                
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            self.logger.error(f"✗ {source} fetch failed: {e}")
            
            # Store error in history
            if self.storage_service:
                self.storage_service.store_external_data_fetch(
                    source=source,
                    status='error',
                    records_fetched=0,
                    message=f"Error: {str(e)}"
                )
        
        return result
    
    def fetch_all_sources(self) -> Dict:
        """Fetch data from all external sources"""
        results = {
            'timestamp': datetime.utcnow().isoformat(),
            'sources': {}
        }
        
        # OFAC Sanctions
        try:
            results['sources']['ofac_sdn'] = self.ofac.fetch_sdn_list()
            self.logger.info(f"✓ Fetched {results['sources']['ofac_sdn']['count']} OFAC SDN entries")
        except Exception as e:
            self.logger.error(f"✗ OFAC SDN fetch failed: {e}")
            results['sources']['ofac_sdn'] = {'error': str(e)}
        
        # FATF High-Risk Countries
        try:
            results['sources']['fatf_high_risk'] = self.fatf.fetch_high_risk_jurisdictions()
            results['sources']['fatf_monitored'] = self.fatf.fetch_monitored_jurisdictions()
            self.logger.info(f"✓ Fetched FATF risk jurisdictions")
        except Exception as e:
            self.logger.error(f"✗ FATF fetch failed: {e}")
            results['sources']['fatf'] = {'error': str(e)}
        
        # RBI Circulars
        try:
            results['sources']['rbi_circulars'] = self.rbi.fetch_recent_circulars(category='AML', limit=20)
            self.logger.info(f"✓ Fetched {results['sources']['rbi_circulars']['count']} RBI circulars")
        except Exception as e:
            self.logger.error(f"✗ RBI fetch failed: {e}")
            results['sources']['rbi_circulars'] = {'error': str(e)}
        
        return results
    
    def process_and_store(self, data: Dict) -> Dict:
        """
        Process fetched data and store as policy documents
        Converts external data into PolicyLens format
        """
        processed = {
            'timestamp': datetime.utcnow().isoformat(),
            'processed_sources': []
        }
        
        # Process OFAC data into policy format
        if 'ofac_sdn' in data['sources'] and 'error' not in data['sources']['ofac_sdn']:
            ofac_policy = self._convert_ofac_to_policy(data['sources']['ofac_sdn'])
            if self.document_processor:
                # Store as policy document
                processed['processed_sources'].append({
                    'source': 'OFAC_SDN',
                    'policy_id': 'POL-OFAC-SDN',
                    'status': 'processed'
                })
        
        # Process FATF data
        if 'fatf_high_risk' in data['sources']:
            fatf_policy = self._convert_fatf_to_policy(
                data['sources']['fatf_high_risk'],
                data['sources'].get('fatf_monitored', {})
            )
            processed['processed_sources'].append({
                'source': 'FATF',
                'policy_id': 'POL-FATF-RISK',
                'status': 'processed'
            })
        
        # Process RBI data
        if 'rbi_circulars' in data['sources'] and 'error' not in data['sources']['rbi_circulars']:
            rbi_policy = self._convert_rbi_to_policy(data['sources']['rbi_circulars'])
            processed['processed_sources'].append({
                'source': 'RBI',
                'policy_id': 'POL-RBI-AML',
                'status': 'processed'
            })
        
        return processed
    
    def _convert_ofac_to_policy(self, ofac_data: Dict) -> str:
        """Convert OFAC sanctions data to policy text"""
        entities = ofac_data.get('data', [])
        
        policy_text = f"""
# OFAC Sanctions List Policy

**Source:** U.S. Department of Treasury - Office of Foreign Assets Control
**Last Updated:** {ofac_data.get('fetched_at')}
**Total Entities:** {ofac_data.get('count')}

## Overview
This policy contains the list of Specially Designated Nationals (SDN) and blocked persons
subject to U.S. sanctions. Transactions with these entities are prohibited.

## Sanctioned Entities

"""
        # Add top entries as examples
        for entity in entities[:100]:  # Limit for policy text
            policy_text += f"\n- **{entity.get('name')}** (Type: {entity.get('type')}, Program: {entity.get('program')})"
        
        policy_text += f"\n\n... and {len(entities) - 100} more entities"
        
        return policy_text
    
    def _convert_fatf_to_policy(self, high_risk: Dict, monitored: Dict) -> str:
        """Convert FATF jurisdictions to policy text"""
        policy_text = f"""
# FATF High-Risk and Monitored Jurisdictions Policy

**Source:** Financial Action Task Force (FATF)
**Last Updated:** {high_risk.get('fetched_at')}

## High-Risk Jurisdictions (Call for Action)

The following jurisdictions have significant strategic deficiencies in their AML/CFT regimes.
Enhanced due diligence is required for transactions involving these countries.

"""
        for country in high_risk.get('data', []):
            policy_text += f"\n- **{country.get('country')}**: {country.get('description')}"
        
        policy_text += "\n\n## Jurisdictions Under Increased Monitoring\n"
        
        for country in monitored.get('data', [])[:20]:  # Limit
            policy_text += f"\n- {country.get('country')}"
        
        return policy_text
    
    def _convert_rbi_to_policy(self, rbi_data: Dict) -> str:
        """Convert RBI circulars to policy text"""
        circulars = rbi_data.get('data', [])
        
        policy_text = f"""
# Reserve Bank of India - AML/KYC Circulars

**Source:** Reserve Bank of India
**Category:** {rbi_data.get('category')}
**Last Updated:** {rbi_data.get('fetched_at')}
**Total Circulars:** {rbi_data.get('count')}

## Recent Master Circulars and Updates

"""
        for circular in circulars:
            policy_text += f"\n### {circular.get('circular_no')} - {circular.get('date')}"
            policy_text += f"\n**Title:** {circular.get('title')}"
            if circular.get('url'):
                policy_text += f"\n**URL:** {circular.get('url')}"
            policy_text += "\n"
        
        return policy_text
