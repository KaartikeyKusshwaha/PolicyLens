"""
Data Scheduler Service
Manages scheduled fetching and updates of external data sources
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import json

from services.external_data_sources import ExternalDataManager
from services.storage_service import StorageService

logger = logging.getLogger(__name__)


class DataScheduler:
    """
    Scheduler for automatic data source updates
    Manages periodic fetching of OFAC, FATF, RBI and other sources
    """
    
    def __init__(self, 
                 external_data_manager: ExternalDataManager,
                 storage_service: StorageService,
                 document_processor=None):
        self.external_data_manager = external_data_manager
        self.storage_service = storage_service
        self.document_processor = document_processor
        self.scheduler = AsyncIOScheduler()
        self.last_fetch_times = {}
        self.fetch_history = []
        
        logger.info("Data Scheduler initialized")
    
    def start(self):
        """Start the scheduler with configured jobs"""
        
        # Schedule OFAC updates - Hourly
        self.scheduler.add_job(
            self.fetch_ofac_data,
            IntervalTrigger(hours=1),
            id='ofac_hourly',
            name='OFAC Hourly Update',
            replace_existing=True
        )
        logger.info("✓ Scheduled OFAC hourly updates")
        
        # Schedule FATF updates - Every 6 hours
        self.scheduler.add_job(
            self.fetch_fatf_data,
            IntervalTrigger(hours=6),
            id='fatf_periodic',
            name='FATF Periodic Update',
            replace_existing=True
        )
        logger.info("✓ Scheduled FATF updates every 6 hours")
        
        # Schedule RBI updates - Every 6 hours
        self.scheduler.add_job(
            self.fetch_rbi_data,
            IntervalTrigger(hours=6),
            id='rbi_periodic',
            name='RBI Periodic Update',
            replace_existing=True
        )
        logger.info("✓ Scheduled RBI updates every 6 hours")
        
        # Initial fetch on startup (delayed by 30 seconds)
        self.scheduler.add_job(
            self.fetch_all_sources,
            'date',
            run_date=datetime.now() + timedelta(seconds=30),
            id='initial_fetch',
            name='Initial Data Fetch',
            replace_existing=True
        )
        logger.info("✓ Scheduled initial data fetch in 30 seconds")
        
        self.scheduler.start()
        logger.info("🚀 Data Scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.scheduler.shutdown()
        logger.info("Data Scheduler stopped")
    
    async def fetch_ofac_data(self):
        """Fetch OFAC sanctions data"""
        logger.info("Starting OFAC data fetch...")
        
        try:
            start_time = datetime.utcnow()
            
            # Fetch OFAC SDN list
            sdn_data = self.external_data_manager.ofac.fetch_sdn_list()
            
            # Convert to policy format
            policy_text = self.external_data_manager._convert_ofac_to_policy(sdn_data)
            
            # Store raw data
            self._save_raw_data('ofac_sdn', sdn_data)
            
            # Process into policy document if processor available
            if self.document_processor:
                await self._process_as_policy(
                    doc_id='POL-OFAC-SDN',
                    title='OFAC Sanctions List',
                    content=policy_text,
                    source='OFAC',
                    topic='SANCTIONS'
                )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            self._record_fetch('OFAC', 'success', duration, sdn_data['count'])
            
            logger.info(f"✓ OFAC data fetched successfully: {sdn_data['count']} entities in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"✗ OFAC data fetch failed: {e}")
            self._record_fetch('OFAC', 'failed', 0, 0, str(e))
    
    async def fetch_fatf_data(self):
        """Fetch FATF high-risk jurisdictions"""
        logger.info("Starting FATF data fetch...")
        
        try:
            start_time = datetime.utcnow()
            
            # Fetch FATF data
            high_risk = self.external_data_manager.fatf.fetch_high_risk_jurisdictions()
            monitored = self.external_data_manager.fatf.fetch_monitored_jurisdictions()
            
            # Convert to policy format
            policy_text = self.external_data_manager._convert_fatf_to_policy(high_risk, monitored)
            
            # Store raw data
            self._save_raw_data('fatf_high_risk', high_risk)
            self._save_raw_data('fatf_monitored', monitored)
            
            # Process into policy document
            if self.document_processor:
                await self._process_as_policy(
                    doc_id='POL-FATF-RISK',
                    title='FATF High-Risk Jurisdictions',
                    content=policy_text,
                    source='FATF',
                    topic='AML'
                )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            total_count = high_risk['count'] + monitored['count']
            self._record_fetch('FATF', 'success', duration, total_count)
            
            logger.info(f"✓ FATF data fetched successfully: {total_count} jurisdictions in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"✗ FATF data fetch failed: {e}")
            self._record_fetch('FATF', 'failed', 0, 0, str(e))
    
    async def fetch_rbi_data(self):
        """Fetch RBI circulars"""
        logger.info("Starting RBI data fetch...")
        
        try:
            start_time = datetime.utcnow()
            
            # Fetch RBI circulars
            circulars = self.external_data_manager.rbi.fetch_recent_circulars(category='AML', limit=50)
            
            # Convert to policy format
            policy_text = self.external_data_manager._convert_rbi_to_policy(circulars)
            
            # Store raw data
            self._save_raw_data('rbi_circulars', circulars)
            
            # Process into policy document
            if self.document_processor:
                await self._process_as_policy(
                    doc_id='POL-RBI-AML',
                    title='RBI AML/KYC Circulars',
                    content=policy_text,
                    source='RBI',
                    topic='AML'
                )
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            self._record_fetch('RBI', 'success', duration, circulars['count'])
            
            logger.info(f"✓ RBI data fetched successfully: {circulars['count']} circulars in {duration:.2f}s")
            
        except Exception as e:
            logger.error(f"✗ RBI data fetch failed: {e}")
            self._record_fetch('RBI', 'failed', 0, 0, str(e))
    
    async def fetch_all_sources(self):
        """Fetch data from all external sources"""
        logger.info("Starting full data sync from all sources...")
        
        start_time = datetime.utcnow()
        
        # Run all fetches
        await self.fetch_ofac_data()
        await self.fetch_fatf_data()
        await self.fetch_rbi_data()
        
        duration = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"✓ Full data sync completed in {duration:.2f}s")
        
        # Save sync report
        self._save_sync_report()
    
    def _save_raw_data(self, source_name: str, data: Dict):
        """Save raw fetched data to storage"""
        try:
            file_path = f"external_data/{source_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
            self.storage_service.save_json(data, file_path)
            logger.info(f"Saved raw data to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save raw data for {source_name}: {e}")
    
    async def _process_as_policy(self, doc_id: str, title: str, content: str, source: str, topic: str):
        """Process external data as a policy document"""
        try:
            # Use document processor to chunk and embed
            chunks = self.document_processor.chunk_document(content)
            
            # This would normally upload to Milvus
            # For now, just log
            logger.info(f"Processed {len(chunks)} chunks for {doc_id}")
            
            # Could trigger policy update here if needed
            
        except Exception as e:
            logger.error(f"Failed to process policy {doc_id}: {e}")
    
    def _record_fetch(self, source: str, status: str, duration: float, count: int, error: str = None):
        """Record fetch history for monitoring"""
        record = {
            'timestamp': datetime.utcnow().isoformat(),
            'source': source,
            'status': status,
            'duration_seconds': duration,
            'records_fetched': count,
            'error': error
        }
        
        self.fetch_history.append(record)
        self.last_fetch_times[source] = datetime.utcnow()
        
        # Keep only last 100 records
        if len(self.fetch_history) > 100:
            self.fetch_history = self.fetch_history[-100:]
    
    def _save_sync_report(self):
        """Save synchronization report"""
        try:
            report = {
                'timestamp': datetime.utcnow().isoformat(),
                'last_fetch_times': {
                    source: time.isoformat() 
                    for source, time in self.last_fetch_times.items()
                },
                'recent_history': self.fetch_history[-20:]  # Last 20 fetches
            }
            
            self.storage_service.save_json(report, 'external_data/sync_report.json')
            logger.info("Sync report saved")
            
        except Exception as e:
            logger.error(f"Failed to save sync report: {e}")
    
    def get_status(self) -> Dict:
        """Get current scheduler status"""
        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                'trigger': str(job.trigger)
            })
        
        return {
            'running': self.scheduler.running,
            'jobs': jobs,
            'last_fetch_times': {
                source: time.isoformat() 
                for source, time in self.last_fetch_times.items()
            },
            'recent_fetches': self.fetch_history[-10:]  # Last 10
        }
    
    def trigger_manual_fetch(self, source: Optional[str] = None):
        """Manually trigger a data fetch"""
        if source == 'OFAC':
            asyncio.create_task(self.fetch_ofac_data())
        elif source == 'FATF':
            asyncio.create_task(self.fetch_fatf_data())
        elif source == 'RBI':
            asyncio.create_task(self.fetch_rbi_data())
        else:
            asyncio.create_task(self.fetch_all_sources())
        
        logger.info(f"Manual fetch triggered for {source or 'all sources'}")
