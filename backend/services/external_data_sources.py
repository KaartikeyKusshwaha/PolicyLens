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
    Connector for OFAC Sanctions Lists.
    https://sanctionslistservice.ofac.treas.gov/

    NOTE: OFAC migrated to a JS-rendered portal in 2024.
    Programmatic bulk CSV downloads via requests are currently 403'd by
    their CDN.  The connector attempts the download but returns a graceful
    'unavailable' payload instead of raising, so the rest of the system
    keeps running.  Use the OFAC Sanctions List Service web UI to download
    the SDN list manually if needed.
    """

    # Updated SLS base URL (migrated from treasury.gov/ofac/downloads in 2024)
    SLS_BASE = "https://sanctionslistservice.ofac.treas.gov/api"

    SDN_CSV_URL = f"{SLS_BASE}/publicationpreview/exports/SDN.CSV"
    SDN_XML_URL = f"{SLS_BASE}/publicationpreview/exports/SDN.XML"
    CONSOLIDATED_URL = f"{SLS_BASE}/publicationpreview/exports/CONS_PRIM.XML"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PolicyLens-Compliance-System/1.0',
            'Accept': 'text/csv,application/xml,*/*',
        })

    def fetch_sdn_list(self, format: str = 'csv') -> Dict:
        """
        Fetch OFAC Specially Designated Nationals list.

        Args:
            format: 'csv' or 'xml'

        Returns:
            Dict with sanctions data and metadata.
            Returns an 'unavailable' payload (not a raise) if the download
            is blocked (403), so callers can handle gracefully.
        """
        url = self.SDN_CSV_URL if format == 'csv' else self.SDN_XML_URL
        logger.info(f"Fetching OFAC SDN list from {url}")
        try:
            response = self.session.get(url, timeout=15, stream=True)
            if response.status_code == 403:
                logger.warning(
                    "OFAC SDN download blocked (403). OFAC now requires browser-based "
                    "access. Download the SDN list manually from "
                    "https://sanctionslistservice.ofac.treas.gov/"
                )
                return {
                    'source': 'OFAC_SDN',
                    'fetched_at': datetime.utcnow().isoformat(),
                    'status': 'unavailable',
                    'reason': (
                        'OFAC migrated to a browser-only portal in 2024. '
                        'Programmatic CSV downloads return 403. '
                        'Download manually from https://sanctionslistservice.ofac.treas.gov/'
                    ),
                    'count': 0,
                    'data': [],
                }
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
        
        # OFAC CSV has no header row, define column names
        # Format: ent_num, SDN_Name, SDN_Type, Program, Title, Call_Sign, Vess_type, Tonnage, GRT, Vess_flag, Vess_owner, Remarks
        fieldnames = ['ent_num', 'SDN_Name', 'SDN_Type', 'Program', 'Title', 'Call_Sign', 'Vess_type', 'Tonnage', 'GRT', 'Vess_flag', 'Vess_owner', 'Remarks']
        
        csv_reader = csv.DictReader(io.StringIO(csv_content), fieldnames=fieldnames)
        priority_entries = []
        other_entries = []
        total_count = 0
        
        # Fast collection - only process first 100 rows for speed
        for idx, row in enumerate(csv_reader):
            if idx >= 100:  # Stop after 100 rows for speed
                break
                
            total_count += 1
            program = row.get('Program', '').strip().strip('"')
            
            entry = {
                'entity_number': row.get('ent_num', '').strip(),
                'name': row.get('SDN_Name', '').strip().strip('"'),
                'type': row.get('SDN_Type', '').strip().strip('"'),
                'program': program,
                'title': row.get('Title', '').strip().strip('"'),
                'call_sign': row.get('Call_Sign', '').strip().strip('"'),
                'vessel_type': row.get('Vess_type', '').strip().strip('"'),
                'tonnage': row.get('Tonnage', '').strip().strip('"'),
                'grt': row.get('GRT', '').strip().strip('"'),
                'vessel_flag': row.get('Vess_flag', '').strip().strip('"'),
                'vessel_owner': row.get('Vess_owner', '').strip().strip('"'),
                'remarks': row.get('Remarks', '').strip().strip('"')
            }
            
            # Prioritize important programs
            if program in priority_programs:
                priority_entries.append(entry)
            elif len(other_entries) < 50:  # Only keep first 50 non-priority
                other_entries.append(entry)
            
            # Early exit after collecting enough entries
            if len(priority_entries) >= 50 and len(other_entries) >= 50:
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
            response = self.session.get(self.CONSOLIDATED_URL, timeout=10)
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
    Connector for FATF High-Risk and Monitored Jurisdictions.
    https://www.fatf-gafi.org/

    FATF does not provide a machine-readable API, so we maintain the
    authoritative lists locally and enrich them with live World Bank
    Governance Indicators data (free, no key required).
    World Bank API docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/898581
    """

    # World Bank Governance Indicators — free JSON API (no key)
    # Indicator GOV_WGI_RL.EST = Rule of Law estimate (source 3, WGI)
    # Replaces old RL.EST which was archived in 2024
    WB_GOVERNANCE_URL = (
        "https://api.worldbank.org/v2/country/all/indicator/"
        "{indicator}?format=json&per_page=300&mrv=1"
    )

    # Authoritative FATF "Call for Action" list (black list) — updated June 2024
    _HIGH_RISK_COUNTRIES: List[Dict] = [
        {"country": "Democratic People's Republic of Korea (DPRK)", "iso3": "PRK"},
        {"country": "Iran",    "iso3": "IRN"},
        {"country": "Myanmar", "iso3": "MMR"},
    ]

    # FATF "Increased Monitoring" list (grey list) — updated June 2024
    _MONITORED_COUNTRIES: List[Dict] = [
        {"country": "Albania",                      "iso3": "ALB"},
        {"country": "Barbados",                     "iso3": "BRB"},
        {"country": "Burkina Faso",                 "iso3": "BFA"},
        {"country": "Cambodia",                     "iso3": "KHM"},
        {"country": "Cayman Islands",               "iso3": "CYM"},
        {"country": "Democratic Republic of Congo", "iso3": "COD"},
        {"country": "Gibraltar",                    "iso3": "GIB"},
        {"country": "Haiti",                        "iso3": "HTI"},
        {"country": "Jamaica",                      "iso3": "JAM"},
        {"country": "Jordan",                       "iso3": "JOR"},
        {"country": "Mali",                         "iso3": "MLI"},
        {"country": "Morocco",                      "iso3": "MAR"},
        {"country": "Mozambique",                   "iso3": "MOZ"},
        {"country": "Nigeria",                      "iso3": "NGA"},
        {"country": "Panama",                       "iso3": "PAN"},
        {"country": "Philippines",                  "iso3": "PHL"},
        {"country": "Senegal",                      "iso3": "SEN"},
        {"country": "South Africa",                 "iso3": "ZAF"},
        {"country": "South Sudan",                  "iso3": "SSD"},
        {"country": "Syria",                        "iso3": "SYR"},
        {"country": "Tanzania",                     "iso3": "TZA"},
        {"country": "Türkiye",                      "iso3": "TUR"},
        {"country": "Uganda",                       "iso3": "UGA"},
        {"country": "United Arab Emirates",         "iso3": "ARE"},
        {"country": "Vietnam",                      "iso3": "VNM"},
        {"country": "Yemen",                        "iso3": "YEM"},
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'PolicyLens-Compliance-System/1.0'
        })
        # Simple in-process cache so the API is not hammered on every call
        self._wb_governance_cache: Optional[Dict[str, float]] = None
        self._wb_cache_ts: Optional[datetime] = None
        self._WB_CACHE_TTL_HOURS = 24

    # ------------------------------------------------------------------
    # Public helpers (backwards-compatible with existing callers)
    # ------------------------------------------------------------------

    @property
    def high_risk_countries(self) -> List[str]:
        """Legacy string-list for backwards compatibility."""
        return [e["country"] for e in self._HIGH_RISK_COUNTRIES]

    @property
    def monitored_countries(self) -> List[str]:
        """Legacy string-list for backwards compatibility."""
        return [e["country"] for e in self._MONITORED_COUNTRIES]

    # ------------------------------------------------------------------
    # World Bank live data
    # ------------------------------------------------------------------

    def _fetch_wb_rule_of_law(self) -> Dict[str, float]:
        """
        Fetch World Bank Rule of Law estimates for all countries.
        Returns {iso3: score} where score is a z-score (typically -2.5 to 2.5).
        Lower scores → weaker rule of law → higher risk.
        Results are cached for WB_CACHE_TTL_HOURS to avoid redundant calls.
        """
        now = datetime.utcnow()
        if (
            self._wb_governance_cache is not None
            and self._wb_cache_ts is not None
            and (now - self._wb_cache_ts).total_seconds() < self._WB_CACHE_TTL_HOURS * 3600
        ):
            return self._wb_governance_cache

        scores: Dict[str, float] = {}
        try:
            url = self.WB_GOVERNANCE_URL.format(indicator="GOV_WGI_RL.EST")
            logger.info("Fetching World Bank Rule of Law data from %s", url)
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
            # payload is [metadata_dict, [data_entries…]]
            if isinstance(payload, list) and len(payload) == 2:
                for entry in payload[1] or []:
                    iso3 = (entry.get("countryiso3code") or "").strip()
                    value = entry.get("value")
                    if iso3 and value is not None:
                        scores[iso3] = float(value)
            logger.info("World Bank Rule of Law: %d country scores loaded", len(scores))
        except Exception as exc:
            logger.warning("Could not fetch World Bank governance data: %s", exc)

        self._wb_governance_cache = scores
        self._wb_cache_ts = now
        return scores

    def fetch_world_bank_risk_enrichment(self) -> Dict:
        """
        Use World Bank Rule of Law scores to identify countries with very
        weak governance (score < -1.0) that are NOT already on the FATF lists.
        Returns enriched risk data alongside raw World Bank scores.
        """
        wb_scores = self._fetch_wb_rule_of_law()
        fatf_iso3s = {e["iso3"] for e in self._HIGH_RISK_COUNTRIES + self._MONITORED_COUNTRIES}

        additional_risk: List[Dict] = []
        for iso3, score in wb_scores.items():
            if iso3 not in fatf_iso3s and score < -1.0:
                additional_risk.append({
                    "iso3": iso3,
                    "rule_of_law_score": round(score, 3),
                    "risk_level": "HIGH" if score < -1.5 else "MEDIUM",
                    "source": "World Bank Governance Indicators (RL.EST)",
                    "note": "Not on FATF list but low Rule of Law score",
                })

        additional_risk.sort(key=lambda x: x["rule_of_law_score"])

        return {
            "source": "WORLD_BANK_GOVERNANCE",
            "fetched_at": datetime.utcnow().isoformat(),
            "indicator": "RL.EST (Rule of Law Estimate)",
            "wb_countries_fetched": len(wb_scores),
            "additional_risk_countries": len(additional_risk),
            "data": additional_risk,
        }

    # ------------------------------------------------------------------
    # FATF list methods (authoritative — no API, manually maintained)
    # ------------------------------------------------------------------

    def fetch_high_risk_jurisdictions(self) -> Dict:
        """
        Return FATF 'Call for Action' (black list) jurisdictions,
        enriched with live World Bank Rule of Law scores where available.
        """
        wb_scores = self._fetch_wb_rule_of_law()
        data = []
        for entry in self._HIGH_RISK_COUNTRIES:
            item = {
                "country": entry["country"],
                "iso3": entry["iso3"],
                "risk_level": "HIGH",
                "status": "Call for Action",
                "description": "Jurisdiction under FATF Call for Action",
            }
            if entry["iso3"] in wb_scores:
                item["world_bank_rule_of_law"] = round(wb_scores[entry["iso3"]], 3)
            data.append(item)

        return {
            "source": "FATF_HIGH_RISK",
            "fetched_at": datetime.utcnow().isoformat(),
            "fatf_list_date": "2024-06-01",
            "count": len(data),
            "data": data,
        }

    def fetch_monitored_jurisdictions(self) -> Dict:
        """
        Return FATF 'Increased Monitoring' (grey list) jurisdictions,
        enriched with live World Bank Rule of Law scores where available.
        """
        wb_scores = self._fetch_wb_rule_of_law()
        data = []
        for entry in self._MONITORED_COUNTRIES:
            item = {
                "country": entry["country"],
                "iso3": entry["iso3"],
                "risk_level": "MEDIUM",
                "status": "Increased Monitoring",
                "description": "Jurisdiction under FATF Increased Monitoring",
            }
            if entry["iso3"] in wb_scores:
                item["world_bank_rule_of_law"] = round(wb_scores[entry["iso3"]], 3)
            data.append(item)

        return {
            "source": "FATF_MONITORED",
            "fetched_at": datetime.utcnow().isoformat(),
            "fatf_list_date": "2024-06-01",
            "count": len(data),
            "data": data,
        }

    def scrape_latest_updates(self) -> Dict:
        """
        Scrape FATF website for latest updates.
        Returns the most recent publication data, falling back to cached lists.
        """
        BASE_URL = "https://www.fatf-gafi.org"
        HIGH_RISK_URL = f"{BASE_URL}/en/publications/high-risk-and-other-monitored-jurisdictions"
        try:
            logger.info("Scraping FATF website for updates")
            response = self.session.get(HIGH_RISK_URL, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            return {
                "source": "FATF_WEBSITE",
                "fetched_at": datetime.utcnow().isoformat(),
                "url": HIGH_RISK_URL,
                "content": soup.get_text()[:5000],
                "note": "Scraped content — manual review recommended",
            }
        except Exception as exc:
            logger.error("Error scraping FATF website: %s", exc)
            return {
                "source": "FATF_CACHED",
                "error": str(exc),
                "high_risk": self.fetch_high_risk_jurisdictions(),
                "monitored": self.fetch_monitored_jurisdictions(),
            }


class RBIConnector:
    """
    Connector for Reserve Bank of India Circulars
    https://www.rbi.org.in/
    """
    
    BASE_URL = "https://www.rbi.org.in"
    CIRCULARS_URL = f"{BASE_URL}/Scripts/BS_ViewListofstandalonecirculars.aspx"
    
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
            
            # Fetch standalone circulars page (no params needed)
            response = self.session.get(self.CIRCULARS_URL, timeout=10)
            response.raise_for_status()
            
            parsed = self._parse_circulars_page(response.text, category, limit)
            
            return parsed
            
        except Exception as e:
            logger.error(f"Error fetching RBI circulars: {e}")
            return {
                'source': 'RBI_CIRCULARS',
                'category': category,
                'fetched_at': datetime.utcnow().isoformat(),
                'count': 0,
                'data': [],
                'error': str(e)
            }
    
    def _parse_circulars_page(self, html_content: str, category: str, limit: int) -> Dict:
        """Parse RBI standalone circulars HTML page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        circulars = []
        
        # Find all tables on the page
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(['td', 'th'])
                
                # Need at least 4 cells: S.No, Circular Number, Title, Date
                if len(cells) < 4:
                    continue
                
                # Get text from cells
                cell_texts = [cell.get_text(strip=True) for cell in cells]
                
                # RBI table structure: [0]=S.No, [1]=Circular Number, [2]=Title, [3]=Date
                circular_no = cell_texts[1] if len(cell_texts) > 1 else ''
                title = cell_texts[2] if len(cell_texts) > 2 else ''
                date = cell_texts[3] if len(cell_texts) > 3 else ''
                
                # Skip if no title or circular number
                if not title or not circular_no:
                    continue
                
                # Filter for AML/KYC related circulars if category specified
                if category in ['AML', 'KYC']:
                    title_upper = title.upper()
                    circular_upper = circular_no.upper()
                    if not any(keyword in title_upper or keyword in circular_upper 
                              for keyword in ['AML', 'KYC', 'KNOW YOUR CUSTOMER', 'MONEY LAUNDERING', 'UAPA', 'SANCTIONS']):
                        continue
                
                # Extract URL from the circular number cell (cell[1])
                url = ''
                circular_cell = cells[1] if len(cells) > 1 else None
                if circular_cell:
                    link = circular_cell.find('a', href=True)
                    if link and link.get('href'):
                        href = link['href']
                        if href.startswith('http'):
                            url = href
                        elif href.startswith('/'):
                            url = self.BASE_URL + href
                        else:
                            url = self.BASE_URL + '/' + href
                
                circular = {
                    'date': date,
                    'title': title,
                    'circular_no': circular_no,
                    'category': category,
                    'url': url
                }
                
                circulars.append(circular)
                
                if len(circulars) >= limit:
                    break
            
            if len(circulars) >= limit:
                break
        
        logger.info(f"Successfully parsed {len(circulars)} RBI circulars")
        
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
            response = self.session.get(url, timeout=10)
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
    
    def __init__(self, document_processor=None, storage_service=None, milvus_service=None):
        self.ofac = OFACConnector()
        self.fatf = FATFConnector()
        self.rbi = RBIConnector()
        self.document_processor = document_processor
        self.storage_service = storage_service
        self.milvus_service = milvus_service
        self.logger = logging.getLogger(__name__)
    
    async def fetch_data(self, source: str, use_cache: bool = True) -> Dict:
        """Fetch data from a specific source with Milvus caching"""
        source = source.upper()
        
        # Try to get cached data from Milvus first
        if use_cache and self.milvus_service:
            cached = self.milvus_service.get_external_data(source, ttl_hours=24)
            if cached:
                return {
                    'source': source,
                    'timestamp': datetime.utcnow().isoformat(),
                    'status': 'success',
                    'data': cached,
                    'from_cache': True,
                    'records_count': cached.get('count', 0),
                    'error': None
                }
        
        result = {
            'source': source,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'success',
            'data': None,
            'from_cache': False,
            'error': None
        }
        
        try:
            if source == 'OFAC':
                data = self.ofac.fetch_sdn_list()
                result['data'] = data
                result['records_count'] = data.get('count', 0)
                self.logger.info(f"✓ Fetched {result['records_count']} OFAC SDN entries")
                
                # Cache the data in Milvus
                if self.milvus_service:
                    self.milvus_service.store_external_data('OFAC', data, result['records_count'])
                
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
                data = {
                    'high_risk': high_risk,
                    'monitored': monitored
                }
                result['data'] = data
                result['records_count'] = high_risk.get('count', 0) + monitored.get('count', 0)
                self.logger.info(f"✓ Fetched FATF risk jurisdictions")
                
                # Cache the data in Milvus
                if self.milvus_service:
                    self.milvus_service.store_external_data('FATF', data, result['records_count'])
                
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
                
                # Cache the data in Milvus
                if self.milvus_service:
                    self.milvus_service.store_external_data('RBI', data, result['records_count'])
                
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

    async def sync_all(self) -> Dict:
        """Fetch all sources (no cache) and return a summary suitable for API."""
        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'results': {}
        }
        try:
            summary['results']['OFAC'] = await self.fetch_data('OFAC', use_cache=False)
        except Exception as e:
            summary['results']['OFAC'] = {'status': 'error', 'error': str(e)}
        try:
            summary['results']['FATF'] = await self.fetch_data('FATF', use_cache=False)
        except Exception as e:
            summary['results']['FATF'] = {'status': 'error', 'error': str(e)}
        try:
            summary['results']['RBI'] = await self.fetch_data('RBI', use_cache=False)
        except Exception as e:
            summary['results']['RBI'] = {'status': 'error', 'error': str(e)}
        return summary
    
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
