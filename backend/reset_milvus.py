"""
Reset Milvus collections with correct embedding dimensions
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from pymilvus import connections, utility
from config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_milvus():
    """Drop existing collections and recreate with correct dimensions"""
    try:
        # Connect to Milvus
        logger.info(f"Connecting to Milvus at {settings.milvus_host}:{settings.milvus_port}...")
        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=settings.milvus_port
        )
        logger.info("✅ Connected to Milvus")
        
        # Drop existing collections
        collections_to_drop = ["policy_chunks", "compliance_cases"]
        for collection_name in collections_to_drop:
            if utility.has_collection(collection_name):
                utility.drop_collection(collection_name)
                logger.info(f"✅ Dropped collection: {collection_name}")
            else:
                logger.info(f"ℹ️  Collection does not exist: {collection_name}")
        
        logger.info("\n✅ Milvus reset complete!")
        logger.info("Collections will be recreated automatically when services start.")
        
    except Exception as e:
        logger.error(f"❌ Error resetting Milvus: {e}")
        import traceback
        traceback.print_exc()
    finally:
        connections.disconnect("default")

if __name__ == "__main__":
    reset_milvus()
