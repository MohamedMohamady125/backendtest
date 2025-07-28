from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app import auth, users, branches, gear, threads, payments, notifications, attendance
from app.middleware.logging import LoggingMiddleware
from app import athlete
from app import performance
from app import measurements
from app import coach
from app import head_coach
from app import coach_assignments
from app.performance import replace_all_performance_logs, ReplaceAllLogsInput
from app.deps import get_current_user
from dotenv import load_dotenv
import asyncio
import time

# ✅ ULTRA-OPTIMIZED DATABASE IMPORTS
from app.database import (
    reset_connection_pool, 
    check_database_health, 
    get_pool_status,
    prewarm_connection_pool,
    get_connection_stats,
    cleanup_connections,
    get_db_cursor
)

load_dotenv()

app = FastAPI(title="HFA API", version="2.0-OPTIMIZED")

# ✅ OPTIMIZED CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific origins in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Specific methods
    allow_headers=["*"],
    max_age=3600,  # Cache preflight requests for 1 hour
)

# ✅ Add custom logging middleware
app.add_middleware(LoggingMiddleware)

# ✅ STARTUP EVENT - PRE-WARM CONNECTIONS
@app.on_event("startup")
async def startup_event():
    """Pre-warm database connections for maximum performance"""
    print("🚀 Starting HFA API with performance optimizations...")
    
    # Pre-warm connection pool
    start_time = time.time()
    prewarmed = prewarm_connection_pool(30)  # Pre-warm 30 connections
    warmup_time = time.time() - start_time
    
    print(f"✅ Pre-warmed {prewarmed} database connections in {warmup_time:.3f}s")
    
    # Initial health check
    health = check_database_health()
    print(f"📊 Database health: {health.get('database', 'unknown')}")
    print(f"📊 Performance grade: {health.get('performance_grade', 'unknown')}")
    
    print("🎯 HFA API ready for blazing fast performance!")

# ✅ SHUTDOWN EVENT - CLEANUP
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    print("🔄 Shutting down HFA API...")
    cleanup_connections()
    print("✅ Cleanup completed")

# ✅ Register routers
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(head_coach.router, prefix="/head-coach", tags=["head_coach"])
app.include_router(measurements.router, prefix="/athlete", tags=["measurements"])
app.include_router(performance.router, prefix="/athlete", tags=["performance"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(branches.router, prefix="/branches", tags=["branches"])
app.include_router(coach_assignments.router, prefix="/coaches", tags=["coach-assignments"])
app.include_router(gear.router, prefix="/gear", tags=["gear"])
app.include_router(threads.router, prefix="/threads", tags=["threads"])
app.include_router(payments.router, prefix="/payments", tags=["payments"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(attendance.router, prefix="/attendance", tags=["attendance"])
app.include_router(athlete.router, tags=["athlete"])
app.include_router(coach.router, prefix="/coach", tags=["coach"])

# ✅ ENHANCED ADMIN ENDPOINTS FOR MONITORING
@app.get("/admin/db-health", tags=["admin"])
def database_health_check():
    """
    COMPREHENSIVE database health check with performance metrics
    """
    return check_database_health()

@app.get("/admin/pool-status", tags=["admin"])
def connection_pool_status():
    """
    Detailed connection pool status with performance metrics
    """
    return get_pool_status()

@app.get("/admin/connection-stats", tags=["admin"])
def connection_statistics():
    """
    MySQL connection statistics
    """
    return get_connection_stats()

@app.post("/admin/reset-pool", tags=["admin"])
def emergency_reset_pool():
    """
    EMERGENCY: Reset connection pool if exhausted
    """
    return reset_connection_pool()

@app.post("/admin/prewarm-pool", tags=["admin"])
def prewarm_pool(connections: int = 20):
    """
    Pre-warm connection pool for better performance
    """
    start_time = time.time()
    prewarmed = prewarm_connection_pool(connections)
    warmup_time = time.time() - start_time
    
    return {
        "success": True,
        "connections_prewarmed": prewarmed,
        "warmup_time_ms": round(warmup_time * 1000, 2),
        "message": f"Pre-warmed {prewarmed} connections in {warmup_time:.3f}s"
    }

@app.get("/health", tags=["system"])
def health_check():
    """
    Enhanced health check with performance indicators
    """
    start_time = time.time()
    db_health = check_database_health()
    health_check_time = time.time() - start_time
    
    return {
        "status": "healthy", 
        "message": "HFA API is running with ULTRA optimizations",
        "version": "2.0-OPTIMIZED",
        "health_check_time_ms": round(health_check_time * 1000, 2),
        "database_status": db_health.get("database", "unknown"),
        "performance_grade": db_health.get("performance_grade", "unknown"),
        "timestamp": time.time()
    }

# ✅ SUPER-OPTIMIZED PERFORMANCE LOGS ENDPOINT
@app.get("/athletes/{athlete_id}/performance-logs", tags=["performance"])
async def get_athlete_performance_logs_by_id(
    athlete_id: int,
    user=Depends(get_current_user)
):
    """
    ULTRA-FAST performance logs retrieval
    """
    start_time = time.time()
    
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(
            status_code=403, 
            detail="Only coaches can view athlete performance logs"
        )

    with get_db_cursor() as (cursor, connection):
        try:
            print(f"🔄 FAST lookup for athlete_id: {athlete_id}")
            
            # OPTIMIZATION: Single query to get athlete info and check access
            cursor.execute("""
                SELECT 
                    a.id as athlete_table_id,
                    u.branch_id, 
                    u.name as athlete_name,
                    u.id as user_id
                FROM athletes a
                JOIN users u ON a.user_id = u.id
                WHERE a.id = %s
            """, (athlete_id,))
            
            athlete = cursor.fetchone()
            
            if not athlete:
                raise HTTPException(status_code=404, detail=f"Athlete not found with ID: {athlete_id}")

            # Check branch access for regular coaches
            if user["role"] == "coach" and user["branch_id"] != athlete["branch_id"]:
                raise HTTPException(
                    status_code=403, 
                    detail="You can only view athletes from your branch"
                )

            # OPTIMIZATION: Get performance logs with better indexing
            athlete_table_id = athlete["athlete_table_id"]
            
            cursor.execute("""
                SELECT 
                    id, 
                    meet_name, 
                    meet_date, 
                    event_name, 
                    result_time, 
                    created_at,
                    athlete_id
                FROM performance_logs
                WHERE athlete_id = %s
                ORDER BY meet_date DESC, created_at DESC
            """, (athlete_table_id,))

            logs = cursor.fetchall()
            
            # Clean up result_time efficiently
            for log in logs:
                if log['result_time'] is not None:
                    log['result_time'] = str(log['result_time']).strip()
                else:
                    log['result_time'] = ""

            execution_time = time.time() - start_time
            print(f"⚡ ULTRA-FAST performance logs: {execution_time:.3f}s ({len(logs)} records)")
            
            return logs

        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error getting performance logs: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to fetch performance logs: {str(e)}"
            )

# ✅ SUPER-OPTIMIZED MEASUREMENTS ENDPOINT
@app.get("/athletes/{athlete_id}/measurements", tags=["measurements"])
async def get_athlete_measurements_by_id(
    athlete_id: int,
    user=Depends(get_current_user)
):
    """
    ULTRA-FAST measurements retrieval
    """
    start_time = time.time()
    
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(
            status_code=403, 
            detail="Only coaches can view athlete measurements"
        )

    with get_db_cursor() as (cursor, connection):
        try:
            print(f"🔄 FAST measurements lookup for athlete_id: {athlete_id}")
            
            # OPTIMIZATION: Single query for athlete info and measurements
            cursor.execute("""
                SELECT 
                    a.id as athlete_table_id,
                    u.branch_id, 
                    u.name as athlete_name,
                    u.email as athlete_email,
                    u.id as user_id
                FROM athletes a
                JOIN users u ON a.user_id = u.id
                WHERE a.id = %s
            """, (athlete_id,))
            
            athlete = cursor.fetchone()
            
            if not athlete:
                raise HTTPException(status_code=404, detail=f"Athlete not found with ID: {athlete_id}")

            # Check branch access
            if user["role"] == "coach" and user["branch_id"] != athlete["branch_id"]:
                raise HTTPException(
                    status_code=403, 
                    detail="You can only view athletes from your branch"
                )

            # Get measurements with optimized query
            athlete_table_id = athlete["athlete_table_id"]
            
            cursor.execute("""
                SELECT 
                    id,
                    height,
                    weight,
                    arm,
                    leg,
                    fat,
                    muscle,
                    created_at
                FROM measurement_logs
                WHERE athlete_id = %s
                ORDER BY created_at DESC
            """, (athlete_table_id,))

            measurements = cursor.fetchall()
            
            execution_time = time.time() - start_time
            print(f"⚡ ULTRA-FAST measurements: {execution_time:.3f}s ({len(measurements)} records)")
            
            return {
                "success": True,
                "athlete": {
                    "id": athlete_id,
                    "name": athlete["athlete_name"],
                    "email": athlete["athlete_email"]
                },
                "measurements": measurements,
                "performance": {
                    "execution_time_ms": round(execution_time * 1000, 2),
                    "records_count": len(measurements)
                }
            }

        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error getting measurements: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to fetch measurements: {str(e)}"
            )

@app.get("/athlete/me", tags=["athlete"])
async def get_current_athlete_info(user=Depends(get_current_user)):
    """
    ULTRA-FAST current athlete info
    """
    start_time = time.time()
    
    if user["role"] != "athlete":
        raise HTTPException(
            status_code=403, 
            detail="Only athletes can access this endpoint"
        )

    with get_db_cursor() as (cursor, connection):
        try:
            cursor.execute("""
                SELECT 
                    a.id as athlete_id,
                    u.id as user_id,
                    u.name,
                    u.email,
                    u.branch_id
                FROM athletes a
                JOIN users u ON a.user_id = u.id
                WHERE u.id = %s
            """, (user["id"],))
            
            athlete = cursor.fetchone()
            
            if not athlete:
                raise HTTPException(status_code=404, detail="Athlete record not found")

            execution_time = time.time() - start_time
            print(f"⚡ ULTRA-FAST athlete info: {execution_time:.3f}s")
            
            return athlete

        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error getting athlete info: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to fetch athlete info: {str(e)}"
            )

@app.get("/athlete/measurements", tags=["measurements"])
async def get_athlete_measurements(user=Depends(get_current_user)):
    """
    ULTRA-FAST athlete's own measurements
    """
    start_time = time.time()
    
    if user["role"] != "athlete":
        raise HTTPException(
            status_code=403, 
            detail="Only athletes can access their measurements"
        )

    with get_db_cursor() as (cursor, connection):
        try:
            # OPTIMIZATION: Single query to get athlete ID and latest measurement
            cursor.execute("""
                SELECT 
                    ml.height,
                    ml.weight,
                    ml.arm,
                    ml.leg,
                    ml.fat,
                    ml.muscle,
                    ml.created_at
                FROM athletes a
                JOIN measurement_logs ml ON a.id = ml.athlete_id
                WHERE a.user_id = %s
                ORDER BY ml.created_at DESC
                LIMIT 1
            """, (user["id"],))
            
            latest_measurement = cursor.fetchone()
            
            execution_time = time.time() - start_time
            print(f"⚡ ULTRA-FAST latest measurement: {execution_time:.3f}s")
            
            if latest_measurement:
                return latest_measurement
            else:
                raise HTTPException(status_code=404, detail="No measurements found")

        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error getting measurements: {e}")
            raise HTTPException(
                status_code=500, 
                detail=f"Failed to fetch measurements: {str(e)}"
            )

# ✅ EXISTING ROUTE - OPTIMIZED
@app.post("/athlete/performance-logs/replace-all", tags=["performance"])
async def replace_all_performance_logs_endpoint(
    data: ReplaceAllLogsInput,
    user=Depends(get_current_user)
):
    """OPTIMIZED performance logs replacement"""
    return replace_all_performance_logs(data, user)

@app.get("/")
def root():
    """Root endpoint with performance info"""
    return {
        "message": "HFA API is running with ULTRA optimizations", 
        "version": "2.0-OPTIMIZED",
        "features": [
            "75-connection pool",
            "Connection reuse",
            "Pre-warmed connections", 
            "Ultra-fast queries",
            "Performance monitoring"
        ]
    }

# ✅ PERFORMANCE MONITORING ENDPOINT
@app.get("/admin/performance-overview", tags=["admin"])
def performance_overview():
    """
    Complete performance overview of the system
    """
    start_time = time.time()
    
    # Get all performance metrics
    db_health = check_database_health()
    pool_status = get_pool_status()
    connection_stats = get_connection_stats()
    
    overview_time = time.time() - start_time
    
    return {
        "performance_overview": {
            "database_health": db_health,
            "connection_pool": pool_status,
            "mysql_stats": connection_stats,
            "overview_generation_time_ms": round(overview_time * 1000, 2)
        },
        "recommendations": {
            "excellent": "All systems optimal" if db_health.get("performance_grade") == "A" else None,
            "good": "Performance is good" if db_health.get("performance_grade") == "B" else None,
            "needs_attention": "Consider optimizations" if db_health.get("performance_grade") == "C" else None
        },
        "timestamp": time.time()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)