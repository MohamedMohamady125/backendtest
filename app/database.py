# app/database.py - ULTRA-OPTIMIZED VERSION

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

# OPTIMIZED Connection pool configuration
DB_CONFIG = {
    'host': settings.DB_HOST,
    'user': settings.DB_USER,
    'password': settings.DB_PASSWORD,
    'database': settings.DB_NAME,
    'port': settings.DB_PORT,
    'pool_name': 'ultra_fast_pool',
    'pool_size': 75,  # INCREASED for high concurrency
    'pool_reset_session': True,
    'autocommit': False,
    'charset': 'utf8mb4',
    'use_unicode': True,
    'connect_timeout': 20,  # REDUCED timeout
    'sql_mode': 'STRICT_TRANS_TABLES',
    'buffered': True,
    'raise_on_warnings': False,
    'get_warnings': False,
    # PERFORMANCE OPTIMIZATIONS
    'use_pure': False,  # Use C extension for speed
    'auth_plugin': 'mysql_native_password',
}

# Thread-local storage for connection reuse within requests
_local = threading.local()

# Create connection pool with error handling
try:
    connection_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
    logger.info(f"✅ ULTRA-FAST connection pool created: {DB_CONFIG['pool_size']} connections")
except Exception as e:
    logger.error(f"❌ Failed to create connection pool: {e}")
    connection_pool = None

# LEGACY FUNCTION - Optimized
def get_connection():
    """
    Legacy get_connection function - ULTRA-OPTIMIZED
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
    ULTRA-OPTIMIZED context manager with connection reuse
    """
    connection = None
    cursor = None
    start_time = time.time()
    
    # Try to reuse connection from thread-local storage
    if hasattr(_local, 'connection') and _local.connection:
        try:
            # Test if connection is still alive
            _local.connection.ping(reconnect=False)
            connection = _local.connection
            cursor = connection.cursor(dictionary=dictionary, buffered=True)
            
            # Quick connection reuse
            yield cursor, connection
            
            # Keep connection alive for reuse (don't close)
            if cursor:
                cursor.close()
            return
            
        except Exception:
            # Connection died, clean up and create new one
            try:
                if hasattr(_local, 'connection'):
                    _local.connection.close()
            except:
                pass
            _local.connection = None
    
    try:
        # Get fresh connection from pool
        if connection_pool:
            connection = connection_pool.get_connection()
        else:
            connection = mysql.connector.connect(**{
                k: v for k, v in DB_CONFIG.items() 
                if k not in ['pool_name', 'pool_size', 'pool_reset_session']
            })
        
        # Store in thread-local for reuse
        _local.connection = connection
        
        # Create cursor
        cursor = connection.cursor(dictionary=dictionary, buffered=True)
        
        # Log slow connections
        connect_time = time.time() - start_time
        if connect_time > 0.050:  # REDUCED threshold to 50ms
            logger.warning(f"⚠️ Slow connection: {connect_time:.3f}s")
        elif connect_time < 0.010:
            logger.info(f"🚀 Fast connection: {connect_time:.3f}s")
        
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
        # Only close cursor, keep connection for reuse
        if cursor:
            try:
                cursor.close()
            except:
                pass
        
        # Don't close connection - keep it in thread-local for reuse
        # It will be returned to pool when thread ends

# Pre-warming function
def prewarm_connection_pool(num_connections=20):
    """Pre-warm connection pool for faster startup"""
    if not connection_pool:
        return 0
    
    connections = []
    try:
        logger.info(f"🔄 Pre-warming {num_connections} connections...")
        
        for i in range(num_connections):
            try:
                conn = connection_pool.get_connection()
                # Test the connection
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
                cursor.close()
                connections.append(conn)
            except Exception as e:
                logger.warning(f"Pre-warm connection {i} failed: {e}")
                break
        
        # Return all connections to pool
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

# Connection pool monitoring
def get_pool_status():
    """Monitor connection pool health - ENHANCED"""
    if connection_pool:
        try:
            # Test pool health
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

# Emergency pool reset function - ENHANCED
def reset_connection_pool():
    """Emergency function to reset connection pool"""
    global connection_pool
    
    logger.warning("🔄 Resetting connection pool...")
    
    try:
        # Clear thread-local connections
        if hasattr(_local, 'connection'):
            try:
                _local.connection.close()
            except:
                pass
            _local.connection = None
        
        # Create new pool
        connection_pool = pooling.MySQLConnectionPool(**DB_CONFIG)
        
        # Pre-warm new pool
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

# Health check function - ENHANCED
def check_database_health():
    """Check database and connection pool health - COMPREHENSIVE"""
    try:
        start_time = time.time()
        
        with get_db_cursor() as (cursor, connection):
            # Multiple health checks
            cursor.execute("SELECT 1 as health_check, CONNECTION_ID(), NOW() as current_time")
            result = cursor.fetchone()
            
            # Check a real table
            cursor.execute("SELECT COUNT(*) as user_count FROM users LIMIT 1")
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

# Cleanup function for graceful shutdown
def cleanup_connections():
    """Clean up thread-local connections"""
    if hasattr(_local, 'connection') and _local.connection:
        try:
            _local.connection.close()
        except:
            pass
        _local.connection = None

# Connection statistics
def get_connection_stats():
    """Get detailed connection statistics"""
    try:
        with get_db_cursor() as (cursor, connection):
            cursor.execute("""
                SELECT 
                    VARIABLE_NAME, 
                    VARIABLE_VALUE 
                FROM INFORMATION_SCHEMA.SESSION_STATUS 
                WHERE VARIABLE_NAME IN (
                    'Connections', 
                    'Threads_connected', 
                    'Threads_running',
                    'Uptime'
                )
            """)
            stats = {row['VARIABLE_NAME']: row['VARIABLE_VALUE'] for row in cursor.fetchall()}
            
            return {
                "mysql_stats": stats,
                "pool_status": get_pool_status(),
                "timestamp": time.time()
            }
    except Exception as e:
        return {"error": str(e), "timestamp": time.time()}