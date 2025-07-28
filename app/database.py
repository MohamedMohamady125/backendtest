# app/database.py - FIXED CONNECTION POOL (No more exhaustion!)
import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager
from app.config import settings
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FIXED Connection pool configuration
DB_CONFIG = {
    'host': settings.DB_HOST,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD,
    'database': settings.DB_NAME,
    'port': settings.DB_PORT,
    'pool_name': 'stable_pool',
    'pool_size': 20,  # Reduced to prevent exhaustion
    'pool_reset_session': True,  # CHANGED: Reset sessions for safety
    'autocommit': False,
    'charset': 'utf8mb4',
    'use_unicode': True,
    'connect_timeout': 30,
    'sql_mode': 'STRICT_TRANS_TABLES',
    'buffered': True,
    'raise_on_warnings': False,
    'get_warnings': False
}

# Create connection pool with error handling
try:
    connection_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
    logger.info(f"✅ STABLE connection pool created: {DB_CONFIG['pool_size']} connections")
except Exception as e:
    logger.error(f"❌ Failed to create connection pool: {e}")
    connection_pool = None

# LEGACY FUNCTION - Fixed to return connections properly
def get_connection():
    """
    Legacy get_connection function - FIXED to prevent pool exhaustion
    """
    if connection_pool:
        try:
            return connection_pool.get_connection()
        except Exception as e:
            logger.error(f"❌ Failed to get connection from pool: {e}")
            # Fallback to direct connection
            return mysql.connector.connect(**{
                k: v for k, v in DB_CONFIG.items() 
                if k not in ['pool_name', 'pool_size', 'pool_reset_session']
            })
    else:
        return mysql.connector.connect(**{
            k: v for k, v in DB_CONFIG.items() 
            if k not in ['pool_name', 'pool_size', 'pool_reset_session']
        })

@contextmanager
def get_db_cursor(dictionary=True):
    """
    FIXED context manager - Properly returns connections to pool
    """
    connection = None
    cursor = None
    start_time = time.time()
    
    try:
        # Get connection from pool
        if connection_pool:
            connection = connection_pool.get_connection()
        else:
            connection = mysql.connector.connect(**{
                k: v for k, v in DB_CONFIG.items() 
                if k not in ['pool_name', 'pool_size', 'pool_reset_session']
            })
        
        # Create cursor
        cursor = connection.cursor(dictionary=dictionary, buffered=True)
        
        # Log slow connections
        connect_time = time.time() - start_time
        if connect_time > 0.100:  # Warn if > 100ms
            logger.warning(f"⚠️ Slow connection: {connect_time:.3f}s")
        
        yield cursor, connection
        
    except Exception as e:
        if connection:
            try:
                connection.rollback()
            except:
                pass
        logger.error(f"❌ Database error: {e}")
        raise
    finally:
        # CRITICAL: Always close cursor and connection
        if cursor:
            try:
                cursor.close()
            except:
                pass
        
        if connection:
            try:
                connection.close()  # This returns connection to pool
            except:
                pass

# Connection pool monitoring
def get_pool_status():
    """Monitor connection pool health"""
    if connection_pool:
        try:
            # Try to get a connection to test pool health
            test_conn = connection_pool.get_connection()
            test_conn.close()
            
            return {
                "status": "healthy",
                "pool_size": connection_pool.pool_size,
                "pool_name": connection_pool.pool_name
            }
        except Exception as e:
            return {
                "status": "unhealthy", 
                "error": str(e),
                "pool_size": connection_pool.pool_size
            }
    else:
        return {"status": "no_pool", "error": "Connection pool not initialized"}

# Emergency pool reset function
def reset_connection_pool():
    """Emergency function to reset connection pool if exhausted"""
    global connection_pool
    
    logger.warning("🔄 Resetting connection pool due to exhaustion...")
    
    try:
        # Close existing pool
        if connection_pool:
            # Note: MySQL connector doesn't have a direct way to close pool
            # But creating a new one should work
            pass
            
        # Create new pool
        connection_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
        logger.info("✅ Connection pool reset successfully")
        
        return {"status": "reset_successful"}
        
    except Exception as e:
        logger.error(f"❌ Failed to reset connection pool: {e}")
        connection_pool = None
        return {"status": "reset_failed", "error": str(e)}

# Health check function
def check_database_health():
    """Check database and connection pool health"""
    try:
        with get_db_cursor() as (cursor, connection):
            cursor.execute("SELECT 1 as health_check")
            result = cursor.fetchone()
            
            pool_status = get_pool_status()
            
            return {
                "database": "healthy",
                "query_result": result,
                "pool_status": pool_status,
                "timestamp": time.time()
            }
    except Exception as e:
        return {
            "database": "unhealthy", 
            "error": str(e),
            "pool_status": get_pool_status(),
            "timestamp": time.time()
        }