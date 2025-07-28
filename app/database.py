# app/database.py - FIXED VERSION

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

# FIXED Connection pool configuration - Render limit is 32
DB_CONFIG = {
    'host': settings.DB_HOST,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD,
    'database': settings.DB_NAME,
    'port': settings.DB_PORT,
    'pool_name': 'fast_pool',
    'pool_size': 25,  # FIXED: Reduced to stay within Render's limit of 32
    'pool_reset_session': True,
    'autocommit': False,
    'charset': 'utf8mb4',
    'use_unicode': True,
    'connect_timeout': 20,
    'sql_mode': 'STRICT_TRANS_TABLES',
    'buffered': True,
    'raise_on_warnings': False,
    'get_warnings': False,
    'use_pure': False,  # Use C extension for speed
    'auth_plugin': 'mysql_native_password',
}

# Thread-local storage for connection reuse
_local = threading.local()

# Create connection pool with error handling
try:
    connection_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
    logger.info(f"✅ Connection pool created: {DB_CONFIG['pool_size']} connections")
except Exception as e:
    logger.error(f"❌ Failed to create connection pool: {e}")
    connection_pool = None

def get_connection():
    """Legacy get_connection function"""
    if connection_pool:
        try:
            return connection_pool.get_connection()
        except Exception as e:
            logger.error(f"❌ Failed to get connection from pool: {e}")
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
    """Optimized context manager with connection reuse"""
    connection = None
    cursor = None
    start_time = time.time()
    
    # Try to reuse connection from thread-local storage
    if hasattr(_local, 'connection') and _local.connection:
        try:
            _local.connection.ping(reconnect=False)
            connection = _local.connection
            cursor = connection.cursor(dictionary=dictionary, buffered=True)
            
            yield cursor, connection
            
            if cursor:
                cursor.close()
            return
            
        except Exception:
            try:
                if hasattr(_local, 'connection'):
                    _local.connection.close()
            except:
                pass
            _local.connection = None
    
    try:
        # Get fresh connection
        if connection_pool:
            connection = connection_pool.get_connection()
        else:
            connection = mysql.connector.connect(**{
                k: v for k, v in DB_CONFIG.items() 
                if k not in ['pool_name', 'pool_size', 'pool_reset_session']
            })
        
        _local.connection = connection
        cursor = connection.cursor(dictionary=dictionary, buffered=True)
        
        # Log slow connections
        connect_time = time.time() - start_time
        if connect_time > 0.100:
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
        if cursor:
            try:
                cursor.close()
            except:
                pass

def prewarm_connection_pool(num_connections=10):
    """Pre-warm connection pool - REDUCED for Render limits"""
    if not connection_pool:
        return 0
    
    connections = []
    try:
        logger.info(f"🔄 Pre-warming {num_connections} connections...")
        
        for i in range(min(num_connections, 15)):  # Max 15 for safety
            try:
                conn = connection_pool.get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                connections.append(conn)
            except Exception as e:
                logger.warning(f"Pre-warm connection {i} failed: {e}")
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

def get_pool_status():
    """Monitor connection pool health"""
    if connection_pool:
        try:
            start_time = time.time()
            test_conn = connection_pool.get_connection()
            test_cursor = test_conn.cursor()
            test_cursor.execute("SELECT CONNECTION_ID(), NOW()")
            result = test_cursor.fetchone()
            test_cursor.close()
            test_conn.close()
            test_time = time.time() - start_time
            
            return {
                "status": "healthy",
                "pool_size": connection_pool.pool_size,
                "pool_name": connection_pool.pool_name,
                "test_connection_time_ms": round(test_time * 1000, 2),
                "test_result": result,
                "performance": "excellent" if test_time < 0.050 else "good" if test_time < 0.100 else "slow"
            }
        except Exception as e:
            return {
                "status": "unhealthy", 
                "error": str(e),
                "pool_size": connection_pool.pool_size if connection_pool else 0
            }
    else:
        return {"status": "no_pool", "error": "Connection pool not initialized"}

def reset_connection_pool():
    """Emergency function to reset connection pool"""
    global connection_pool
    
    logger.warning("🔄 Resetting connection pool...")
    
    try:
        if hasattr(_local, 'connection'):
            try:
                _local.connection.close()
            except:
                pass
            _local.connection = None
        
        connection_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
        prewarmed = prewarm_connection_pool(10)
        
        logger.info(f"✅ Connection pool reset successfully, pre-warmed {prewarmed} connections")
        
        return {
            "status": "reset_successful", 
            "prewarmed_connections": prewarmed,
            "pool_size": connection_pool.pool_size
        }
        
    except Exception as e:
        logger.error(f"❌ Failed to reset connection pool: {e}")
        connection_pool = None
        return {"status": "reset_failed", "error": str(e)}

def check_database_health():
    """FIXED health check - simplified query"""
    try:
        start_time = time.time()
        
        with get_db_cursor() as (cursor, connection):
            # FIXED: Simplified health check query
            cursor.execute("SELECT 1 as health_check, CONNECTION_ID()")
            result = cursor.fetchone()
            
            # Simple user count check
            cursor.execute("SELECT COUNT(*) as user_count FROM users")
            user_check = cursor.fetchone()
            
            query_time = time.time() - start_time
            pool_status = get_pool_status()
            
            return {
                "database": "healthy",
                "query_time_ms": round(query_time * 1000, 2),
                "health_check_result": result,
                "user_count": user_check["user_count"] if user_check else 0,
                "pool_status": pool_status,
                "timestamp": time.time(),
                "performance_grade": "A" if query_time < 0.050 else "B" if query_time < 0.100 else "C"
            }
    except Exception as e:
        return {
            "database": "unhealthy", 
            "error": str(e),
            "pool_status": get_pool_status(),
            "timestamp": time.time()
        }

def cleanup_connections():
    """Clean up thread-local connections"""
    if hasattr(_local, 'connection') and _local.connection:
        try:
            _local.connection.close()
        except:
            pass
        _local.connection = None

def get_connection_stats():
    """Get connection statistics - SIMPLIFIED"""
    try:
        with get_db_cursor() as (cursor, connection):
            cursor.execute("SHOW STATUS WHERE Variable_name IN ('Connections', 'Threads_connected')")
            stats = {row['Variable_name']: row['Value'] for row in cursor.fetchall()}
            
            return {
                "mysql_stats": stats,
                "pool_status": get_pool_status(),
                "timestamp": time.time()
            }
    except Exception as e:
        return {"error": str(e), "timestamp": time.time()}