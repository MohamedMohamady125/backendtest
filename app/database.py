# app/database.py - FIXED VERSION (remove unsupported parameters)

import mysql.connector
from mysql.connector import pooling
from app.config import settings
import time

# ✅ FIXED: Remove unsupported parameters
def get_connection():
    """Get database connection with supported parameters only"""
    connection = mysql.connector.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        
        # ✅ CRITICAL: Only use supported parameters
        autocommit=False,  # Explicit transaction control
        
        # Connection pool settings
        pool_name='mypool',
        pool_size=20,
        pool_reset_session=True,  # Reset session state
        
        # Timeouts
        connection_timeout=10,
        
        # Character set
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
        
        # ✅ REMOVED: These are not supported by mysql-connector-python
        # isolation_level='READ-COMMITTED',  # ❌ NOT SUPPORTED
        # sql_mode='...',  # ❌ NOT SUPPORTED IN CONNECTION
    )
    
    # ✅ FIXED: Set session variables AFTER connection is established
    cursor = connection.cursor()
    try:
        # Set isolation level using SQL instead of connection parameter
        cursor.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        cursor.execute("SET SESSION innodb_lock_wait_timeout = 50")
        cursor.execute("SET SESSION lock_wait_timeout = 50")
        
        # Optional: Set SQL mode if needed
        cursor.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION'")
        
        print("✅ Database session configured successfully")
    except Exception as e:
        print(f"⚠️ Warning: Could not set some session variables: {e}")
    finally:
        cursor.close()
    
    return connection

# ✅ ALTERNATIVE: Simple connection without pool (for testing)
def get_simple_connection():
    """Get simple database connection without pooling"""
    try:
        connection = mysql.connector.connect(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            database=settings.DB_NAME,
            autocommit=False,
            charset='utf8mb4',
            collation='utf8mb4_unicode_ci'
        )
        
        print("✅ Simple database connection established")
        return connection
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise

# ✅ CONTEXT MANAGER: For better resource management
from contextlib import contextmanager

@contextmanager
def get_db_cursor():
    """Context manager for database operations"""
    connection = None
    cursor = None
    try:
        connection = get_simple_connection()  # Use simple connection for now
        cursor = connection.cursor(dictionary=True)
        yield cursor, connection
    except Exception as e:
        if connection:
            connection.rollback()
        print(f"❌ Database error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

# ✅ HEALTH CHECK: Test database connectivity
def check_database_health():
    """Check database health and connectivity"""
    try:
        start_time = time.time()
        
        with get_db_cursor() as (cursor, connection):
            cursor.execute("SELECT 1 as health_check")
            result = cursor.fetchone()
            
            if result and result['health_check'] == 1:
                response_time = time.time() - start_time
                return {
                    "database": "healthy",
                    "response_time_ms": round(response_time * 1000, 2),
                    "status": "connected",
                    "performance_grade": "A" if response_time < 0.1 else "B" if response_time < 0.5 else "C"
                }
            else:
                return {
                    "database": "unhealthy",
                    "status": "query_failed"
                }
                
    except Exception as e:
        return {
            "database": "unhealthy",
            "status": "connection_failed",
            "error": str(e)
        }

# ✅ POOL STATUS: Monitor connection pool
def get_pool_status():
    """Get connection pool status"""
    try:
        # Since we're using simple connections now, return basic info
        return {
            "pool_type": "simple_connections",
            "status": "healthy",
            "message": "Using simple connections instead of pool"
        }
    except Exception as e:
        return {
            "pool_type": "unknown",
            "status": "error",
            "error": str(e)
        }

def get_connection_stats():
    """Get MySQL connection statistics"""
    try:
        with get_db_cursor() as (cursor, connection):
            cursor.execute("SHOW STATUS LIKE 'Connections'")
            stats = cursor.fetchall()
            
            return {
                "mysql_stats": {stat['Variable_name']: stat['Value'] for stat in stats},
                "status": "available"
            }
    except Exception as e:
        return {
            "mysql_stats": {},
            "status": "unavailable",
            "error": str(e)
        }

def reset_connection_pool():
    """Reset connection pool (placeholder for simple connections)"""
    return {
        "success": True,
        "message": "Using simple connections - no pool to reset"
    }

def prewarm_connection_pool(connections: int):
    """Prewarm connection pool (placeholder for simple connections)"""
    return connections

def cleanup_connections():
    """Cleanup connections on shutdown"""
    print("🧹 Cleaning up database connections...")
    # With simple connections, nothing to clean up
    print("✅ Cleanup completed")