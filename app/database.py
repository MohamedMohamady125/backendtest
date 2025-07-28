# app/database.py - AGGRESSIVE CONNECTION OPTIMIZATION (Fixed)
import mysql.connector
from mysql.connector import pooling
from contextlib import contextmanager
from app.config import settings
import logging
import time
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AGGRESSIVE Connection pool configuration
DB_CONFIG = {
    'host': settings.DB_HOST,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD,
    'database': settings.DB_NAME,
    'port': settings.DB_PORT,
    'pool_name': 'aggressive_pool',
    'pool_size': 30,  # Increased from 20
    'pool_reset_session': False,  # Skip session reset for speed
    'autocommit': False,
    'charset': 'utf8mb4',
    'use_unicode': True,
    'connect_timeout': 30,  # Increased timeout
    'sql_mode': 'STRICT_TRANS_TABLES',
    # PERFORMANCE OPTIMIZATIONS
    'buffered': True,
    'raise_on_warnings': False,
    'get_warnings': False,
    'connection_timeout': 30
}

# Create larger connection pool
try:
    connection_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
    logger.info(f"✅ AGGRESSIVE connection pool created: {DB_CONFIG['pool_size']} connections")
    
    # Pre-warm the connection pool
    connections = []
    for i in range(5):  # Pre-create 5 connections
        try:
            conn = connection_pool.get_connection()
            connections.append(conn)
        except Exception as e:
            logger.warning(f"Pre-warm connection {i} failed: {e}")
    
    # Return pre-warmed connections
    for conn in connections:
        conn.close()
    
    logger.info("✅ Connection pool pre-warmed")
    
except Exception as e:
    logger.error(f"❌ Failed to create aggressive connection pool: {e}")
    connection_pool = None

# Global connection cache (risky but fast)
_thread_local = threading.local()

# LEGACY FUNCTION - Keep for backward compatibility
def get_connection():
    """
    Legacy get_connection function - kept for backward compatibility
    Other files still import this, so we need to keep it
    """
    if connection_pool:
        return connection_pool.get_connection()
    else:
        return mysql.connector.connect(**{
            k: v for k, v in DB_CONFIG.items() 
            if k not in ['pool_name', 'pool_size', 'pool_reset_session']
        })

def get_cached_connection():
    """
    AGGRESSIVE: Keep one connection per thread (reduces connection overhead)
    WARNING: Use with caution in production
    """
    if not hasattr(_thread_local, 'connection') or not _thread_local.connection.is_connected():
        if connection_pool:
            _thread_local.connection = connection_pool.get_connection()
        else:
            _thread_local.connection = mysql.connector.connect(**{
                k: v for k, v in DB_CONFIG.items() 
                if k not in ['pool_name', 'pool_size', 'pool_reset_session']
            })
    
    return _thread_local.connection

@contextmanager
def get_db_cursor_aggressive(dictionary=True):
    """
    AGGRESSIVE VERSION - Reuses thread-local connections
    """
    start_time = time.time()
    connection = None
    
    try:
        connection = get_cached_connection()
        cursor = connection.cursor(dictionary=dictionary, buffered=True)
        
        connect_time = time.time() - start_time
        if connect_time > 0.050:  # Only warn if > 50ms
            logger.warning(f"⚠️ Connection still slow: {connect_time:.3f}s")
        else:
            logger.debug(f"✅ Fast connection: {connect_time:.3f}s")
        
        yield cursor, connection
        
    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        # DON'T close connection - keep it for reuse

# Keep your existing get_db_cursor for backward compatibility
@contextmanager 
def get_db_cursor(dictionary=True):
    """Use the aggressive version"""
    with get_db_cursor_aggressive(dictionary) as (cursor, connection):
        yield cursor, connection

# Connection health check
def check_connection_health():
    """Check and repair connections"""
    try:
        with get_db_cursor_aggressive() as (cursor, connection):
            cursor.execute("SELECT 1")
            return {"status": "healthy"}
    except Exception as e:
        # Reset thread-local connection on error
        if hasattr(_thread_local, 'connection'):
            delattr(_thread_local, 'connection')
        return {"status": "unhealthy", "error": str(e)}

# Startup optimization
def warm_connection_pool():
    """Pre-warm connections on startup"""
    logger.info("🔥 Warming up connection pool...")
    
    for i in range(10):
        try:
            with get_db_cursor_aggressive() as (cursor, connection):
                cursor.execute("SELECT 1")
            logger.info(f"✅ Warmed connection {i+1}")
        except Exception as e:
            logger.warning(f"❌ Failed to warm connection {i+1}: {e}")
    
    logger.info("🔥 Connection pool warmed!")