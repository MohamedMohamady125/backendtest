# app/database.py - SIMPLIFIED and RELIABLE VERSION

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

# SIMPLIFIED Connection pool configuration
DB_CONFIG = {
    'host': settings.DB_HOST,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD,
    'database': settings.DB_NAME,
    'port': settings.DB_PORT,
    'pool_name': 'simple_pool',
    'pool_size': 15,  # Conservative size for Render
    'pool_reset_session': False,  # Better performance
    'autocommit': False,
    'charset': 'utf8mb4',
    'use_unicode': True,
    'connect_timeout': 10,
    'sql_mode': 'STRICT_TRANS_TABLES',
    'buffered': True,
    'raise_on_warnings': False,
    'get_warnings': False,
    'use_pure': False,
    'auth_plugin': 'mysql_native_password',
}

# Create connection pool
try:
    connection_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
    logger.info(f"✅ Connection pool created: {DB_CONFIG['pool_size']} connections")
except Exception as e:
    logger.error(f"❌ Failed to create connection pool: {e}")
    connection_pool = None

@contextmanager
def get_db_cursor(dictionary=True):
    """Simplified but robust database cursor context manager"""
    connection = None
    cursor = None
    
    try:
        # Try pool first, fallback to direct connection
        if connection_pool:
            try:
                connection = connection_pool.get_connection()
            except mysql.connector.PoolError:
                logger.warning("🔄 Pool exhausted, using direct connection")
                connection = _get_direct_connection()
        else:
            connection = _get_direct_connection()
        
        # Verify connection is alive
        connection.ping(reconnect=True, attempts=2, delay=0.5)
        cursor = connection.cursor(dictionary=dictionary, buffered=True)
        
        yield cursor, connection
        
        # Commit if there's an active transaction
        if connection.in_transaction:
            connection.commit()
            
    except Exception as e:
        # Rollback on error
        if connection and connection.in_transaction:
            try:
                connection.rollback()
            except:
                pass
        logger.error(f"❌ Database error: {e}")
        raise
        
    finally:
        # Always cleanup
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if connection:
            try:
                connection.close()
            except:
                pass

def _get_direct_connection():
    """Get a direct database connection (bypassing pool)"""
    direct_config = {k: v for k, v in DB_CONFIG.items() 
                    if k not in ['pool_name', 'pool_size', 'pool_reset_session']}
    return mysql.connector.connect(**direct_config)

@contextmanager
def get_db_cursor_with_retry(dictionary=True, max_retries=2):
    """Database cursor with simple retry logic"""
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            with get_db_cursor(dictionary=dictionary) as (cursor, connection):
                yield cursor, connection
                return  # Success, exit retry loop
                
        except mysql.connector.PoolError as e:
            last_error = e
            if attempt < max_retries:
                wait_time = 0.1 * (attempt + 1)
                logger.warning(f"⚠️ Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                time.sleep(wait_time)
                continue
            else:
                logger.error(f"❌ All retries failed: {e}")
                raise
                
        except Exception as e:
            last_error = e
            logger.error(f"❌ Non-retryable error: {e}")
            raise
    
    # This should never be reached, but just in case
    if last_error:
        raise last_error

def check_database_health():
    """Simple health check"""
    try:
        start_time = time.time()
        
        with get_db_cursor() as (cursor, connection):
            cursor.execute("SELECT 1 as health_check")
            result = cursor.fetchone()
            
            query_time = time.time() - start_time
            
            return {
                "database": "healthy",
                "query_time_ms": round(query_time * 1000, 2),
                "result": result,
                "pool_size": connection_pool.pool_size if connection_pool else 0,
                "timestamp": time.time()
            }
            
    except Exception as e:
        return {
            "database": "unhealthy", 
            "error": str(e),
            "timestamp": time.time()
        }

def reset_connection_pool():
    """Reset the connection pool"""
    global connection_pool
    
    logger.warning("🔄 Resetting connection pool...")
    
    try:
        connection_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
        logger.info("✅ Connection pool reset successfully")
        return {"status": "success", "pool_size": connection_pool.pool_size}
        
    except Exception as e:
        logger.error(f"❌ Pool reset failed: {e}")
        connection_pool = None
        return {"status": "failed", "error": str(e)}

def get_pool_status():
    """Get pool status"""
    if connection_pool:
        return {
            "status": "available",
            "pool_size": connection_pool.pool_size,
            "pool_name": connection_pool.pool_name
        }
    else:
        return {"status": "unavailable", "pool_size": 0}

# Legacy compatibility
# Add these settings to your database configuration

# In your database.py or connection setup:

def get_connection():
    """Get database connection with strict consistency settings"""
    connection = mysql.connector.connect(
        host=settings.DB_HOST,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        
        # ✅ CRITICAL: Add these for consistency
        autocommit=False,  # Explicit transaction control
        isolation_level='READ-COMMITTED',  # Prevent dirty reads
        sql_mode='STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION',
        
        # Connection pool settings
        pool_name='mypool',
        pool_size=20,
        pool_reset_session=True,  # Reset session state
        
        # Timeouts
        connection_timeout=10,
        
        # Character set
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )
    
    # ✅ CRITICAL: Set session variables for consistency
    cursor = connection.cursor()
    cursor.execute("SET SESSION innodb_lock_wait_timeout = 50")
    cursor.execute("SET SESSION lock_wait_timeout = 50") 
    cursor.execute("SET SESSION tx_isolation = 'READ-COMMITTED'")
    cursor.close()
    
    return connection

# ✅ OPTIONAL: Add a connection wrapper with retry logic
import time
import random

def get_connection_with_retry(max_retries=3):
    """Get database connection with retry logic for better reliability"""
    for attempt in range(max_retries):
        try:
            return get_connection()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            
            wait_time = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff
            print(f"❌ Connection attempt {attempt + 1} failed, retrying in {wait_time:.2f}s...")
            time.sleep(wait_time)
    
    raise Exception("Failed to connect after all retries")

def get_connection_stats():
    """Get basic connection statistics"""
    try:
        with get_db_cursor() as (cursor, connection):
            cursor.execute("""
                SHOW STATUS WHERE Variable_name IN (
                    'Connections', 
                    'Threads_connected', 
                    'Max_used_connections'
                )
            """)
            
            stats = {}
            for row in cursor.fetchall():
                stats[row['Variable_name']] = row['Value']
            
            return {
                "mysql_stats": stats,
                "pool_status": get_pool_status(),
                "timestamp": time.time()
            }
            
    except Exception as e:
        return {"error": str(e), "timestamp": time.time()}

# Optional: Prewarm function (use sparingly)
def prewarm_connection_pool(num_connections=5):
    """Pre-warm a few connections"""
    if not connection_pool:
        return 0
    
    connections = []
    try:
        for i in range(min(num_connections, 5)):  # Max 5 for safety
            try:
                conn = connection_pool.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                connections.append(conn)
            except:
                break
        
        for conn in connections:
            try:
                conn.close()
            except:
                pass
        
        logger.info(f"✅ Pre-warmed {len(connections)} connections")
        return len(connections)
        
    except Exception as e:
        logger.error(f"❌ Pre-warming failed: {e}")
        return 0

# Thread-local storage for compatibility
_local = threading.local()

def cleanup_connections():
    """Clean up thread-local connections (compatibility function)"""
    if hasattr(_local, 'connection') and _local.connection:
        try:
            _local.connection.close()
        except:
            pass
        _local.connection = None

def force_pool_cleanup():
    """Force cleanup of all pool connections"""
    global connection_pool
    if connection_pool:
        try:
            # Try to reset the pool
            reset_connection_pool()
            logger.info("🧹 Forced pool cleanup completed")
        except Exception as e:
            logger.error(f"❌ Pool cleanup failed: {e}")

def monitor_pool_health():
    """Monitor pool health and auto-recover if needed"""
    try:
        status = get_pool_status()
        if status.get("status") != "available":
            logger.warning("⚠️ Pool unhealthy, attempting reset...")
            reset_connection_pool()
        return status
    except Exception as e:
        logger.error(f"❌ Pool monitoring failed: {e}")
        return {"status": "monitoring_failed", "error": str(e)}