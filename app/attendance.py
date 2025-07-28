from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from app.deps import get_current_user
from app.database import get_connection
from app.utils.auth_utils import can_access_branch
from pydantic import BaseModel
from datetime import date, timedelta
import traceback
import json

router = APIRouter()

WEEKDAY_MAP = {
    "Mon": 0,
    "Tue": 1,
    "Wed": 2,
    "Thu": 3,
    "Fri": 4,
    "Sat": 5,
    "Sun": 6,
}

def get_branch_session_dates(practice_days_str: str) -> list[str]:
    today = date.today()
    offset = (today.weekday() - 4) % 7  # Last Friday
    last_friday = today - timedelta(days=offset)

    # Safely split by commas to extract day names
    extracted_days = []
    for entry in practice_days_str.split(","):
        parts = entry.strip().split(":")
        if parts:
            weekday_part = parts[0].strip()
            # Match day names to known weekday map (e.g., Sat, Mon, etc.)
            for key in WEEKDAY_MAP:
                if key.lower() in weekday_part.lower():
                    extracted_days.append(key)
                    break

    session_dates = []
    for day in extracted_days[:3]:  # limit to 3
        weekday_num = WEEKDAY_MAP[day]
        delta = (weekday_num - 4) % 7
        session_date = last_friday + timedelta(days=delta)
        session_dates.append(session_date.isoformat())

    return session_dates

class AttendanceMark(BaseModel):
    athlete_id: int
    session_date: str
    status: str
    notes: str = None

def _fetch_attendance_sync(branch_id: int, session_date: str, user_id: int):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Get all athletes in the branch
        cursor.execute("""
            SELECT a.id as athlete_id, u.name as athlete_name
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE u.branch_id = %s AND u.approved = 1
            ORDER BY u.name
        """, (branch_id,))
        athletes = cursor.fetchall()

        # Get existing attendance records for this date
        cursor.execute("""
            SELECT athlete_id, status, notes 
            FROM attendance 
            WHERE session_date = %s AND branch_id = %s
        """, (session_date, branch_id))
        existing = cursor.fetchall()
        existing_map = {x["athlete_id"]: {"status": x["status"], "notes": x["notes"]} for x in existing}

        # Seed missing records
        to_seed = [
            (a["athlete_id"], session_date, branch_id, user_id) 
            for a in athletes 
            if a["athlete_id"] not in existing_map
        ]
        
        if to_seed:
            for record in to_seed:
                cursor.execute("""
                    INSERT INTO attendance (athlete_id, session_date, status, branch_id, recorded_by)
                    VALUES (%s, %s, NULL, %s, %s)
                    ON DUPLICATE KEY UPDATE status = status
                """, record)
            conn.commit()

        # Get final result with attendance data
        cursor.execute("""
            SELECT 
                a.id AS athlete_id, 
                u.name AS athlete_name, 
                att.status,
                att.notes
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            LEFT JOIN attendance att ON att.athlete_id = a.id 
                AND att.session_date = %s AND att.branch_id = %s
            WHERE u.branch_id = %s AND u.approved = 1
            ORDER BY u.name
        """, (session_date, branch_id, branch_id))
        
        result = cursor.fetchall()
        return result
        
    finally:
        cursor.close()
        conn.close()

@router.get("/weekly/session-dates")
def get_weekly_session_dates(user=Depends(get_current_user)):
    """Get session dates for the current user's branch"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Get the user's branch_id
        branch_id = user["branch_id"]
        if not branch_id:
            raise HTTPException(status_code=400, detail="User has no branch assigned")
        
        # Get practice days for the branch
        cursor.execute("SELECT practice_days FROM branches WHERE id = %s", (branch_id,))
        row = cursor.fetchone()
        
        if not row or not row["practice_days"]:
            raise HTTPException(status_code=404, detail="Practice days not set for this branch")

        return get_branch_session_dates(row["practice_days"])
        
    finally:
        cursor.close()
        conn.close()

@router.get("/branch/{branch_id}/session-dates")
def get_branch_session_dates_api(branch_id: int, user=Depends(get_current_user)):
    """Get session dates for a specific branch"""
    can_access_branch(user, branch_id)
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT practice_days FROM branches WHERE id = %s", (branch_id,))
        row = cursor.fetchone()
        
        if not row or not row["practice_days"]:
            raise HTTPException(status_code=404, detail="Practice days not set")

        return get_branch_session_dates(row["practice_days"])
        
    finally:
        cursor.close()
        conn.close()

@router.get("/day/{session_date}")
async def get_day_attendance(session_date: str, user=Depends(get_current_user)):
    """Get attendance for a specific day for the current user's branch"""
    branch_id = user["branch_id"]
    if not branch_id:
        raise HTTPException(status_code=400, detail="User has no branch assigned")
    
    return await run_in_threadpool(_fetch_attendance_sync, branch_id, session_date, user["id"])

@router.get("/branch/{branch_id}/day/{session_date}")
async def get_attendance_by_day(branch_id: int, session_date: str, user=Depends(get_current_user)):
    """Get attendance for a specific day and branch"""
    can_access_branch(user, branch_id)
    return await run_in_threadpool(_fetch_attendance_sync, branch_id, session_date, user["id"])

def _mark_attendance_sync(data: AttendanceMark, user: dict):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # Verify athlete belongs to coach's branch
        cursor.execute("""
            SELECT u.branch_id FROM athletes a 
            JOIN users u ON a.user_id = u.id 
            WHERE a.id = %s
        """, (data.athlete_id,))
        res = cursor.fetchone()
        
        if not res:
            raise HTTPException(status_code=404, detail="Athlete not found")
        if int(res["branch_id"]) != int(user["branch_id"]):
            raise HTTPException(status_code=403, detail="You can only mark attendance for athletes in your branch")

        # Insert or update attendance record
        cursor.execute("""
            INSERT INTO attendance (athlete_id, session_date, status, branch_id, recorded_by, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
                status = VALUES(status), 
                recorded_by = VALUES(recorded_by),
                notes = VALUES(notes)
        """, (
            data.athlete_id, 
            data.session_date, 
            data.status, 
            user["branch_id"], 
            user["id"],
            data.notes
        ))

        conn.commit()
        
        print(f"🔄 Attendance marked: athlete_id={data.athlete_id}, date={data.session_date}, status={data.status}")
        
        return {"message": "Attendance updated successfully"}
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error marking attendance: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

@router.post("/mark")
async def mark_attendance(data: AttendanceMark, user=Depends(get_current_user)):
    """Mark attendance for an athlete"""
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can mark attendance")
    return await run_in_threadpool(_mark_attendance_sync, data, user)

@router.get("/athlete/{user_id}/week")
def get_athlete_weekly_attendance(user_id: int, user=Depends(get_current_user)):
    """Get weekly attendance for an athlete"""
    # Allow athletes to access their own data OR coaches/head_coaches to access any athlete in their branch
    if user["id"] != user_id and user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Access denied")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT a.id AS athlete_id, u.branch_id
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE u.id = %s
        """, (user_id,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Athlete profile not found")

        athlete_id = result["athlete_id"]
        branch_id = result["branch_id"]

        # Additional check: if user is coach/head_coach, ensure they're in the same branch
        if user["role"] in ["coach", "head_coach"] and user["id"] != user_id:
            if user["branch_id"] != branch_id:
                raise HTTPException(status_code=403, detail="Cannot access athletes from other branches")

        cursor.execute("SELECT practice_days FROM branches WHERE id = %s", (branch_id,))
        branch = cursor.fetchone()

        if not branch or not branch["practice_days"]:
            raise HTTPException(status_code=400, detail="Branch has no practice days configured")

        session_dates = get_branch_session_dates(branch["practice_days"])

        records = []
        for i, session_date in enumerate(session_dates):
            cursor.execute("""
                SELECT status
                FROM attendance
                WHERE athlete_id = %s AND session_date = %s
            """, (athlete_id, session_date))
            row = cursor.fetchone()
            records.append({"day_number": i + 1, "status": row["status"] if row else None})

        return records

    except Exception as e:
        print(f"🔍 DEBUG - Attendance error for user {user_id}:")
        print(f"   - User role: {user['role']}")
        print(f"   - User ID: {user['id']}")
        print(f"   - User branch: {user['branch_id']}")
        print(f"   - Error: {str(e)}")
        raise

    finally:
        cursor.close()
        conn.close()

@router.get("/branch/{branch_id}/summary")
def get_attendance_summary(branch_id: int, user=Depends(get_current_user)):
    """Get attendance summary for a branch"""
    can_access_branch(user, branch_id)

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        cursor.execute("SELECT practice_days FROM branches WHERE id = %s", (branch_id,))
        branch = cursor.fetchone()
        if not branch or not branch["practice_days"]:
            raise HTTPException(status_code=404, detail="Practice days not set")

        session_dates = get_branch_session_dates(branch["practice_days"])

        query = """
            SELECT 
                a.id AS athlete_id,
                u.name AS athlete_name,
                u.email,
                at.session_date,
                at.status
            FROM athletes a
            JOIN users u ON a.user_id = u.id
            LEFT JOIN attendance at
              ON at.athlete_id = a.id AND at.branch_id = %s AND at.session_date IN (%s, %s, %s)
            WHERE u.branch_id = %s AND u.approved = 1
            ORDER BY u.name, at.session_date
        """
        cursor.execute(query, (branch_id, *session_dates, branch_id))
        rows = cursor.fetchall()

        return {
            "records": rows,
            "session_dates": session_dates
        }

    finally:
        cursor.close()
        conn.close()

from fastapi import Query

@router.get("/athlete/{athlete_id}/monthly")
def get_athlete_monthly_attendance(
    athlete_id: int,
    year: int = Query(..., description="Year, e.g. 2024"),
    month: int = Query(..., description="Month, e.g. 7"),
    user=Depends(get_current_user),
):
    """Get monthly attendance for an athlete"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT u.branch_id FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE a.id = %s
        """, (athlete_id,))
        info = cursor.fetchone()
        if not info:
            raise HTTPException(status_code=404, detail="Athlete not found")
        branch_id = info["branch_id"]

        # Check access permissions
        if user["role"] == "athlete":
            # Athletes can only access their own data
            cursor.execute("""
                SELECT a.id FROM athletes a
                JOIN users u ON a.user_id = u.id
                WHERE a.id = %s AND u.id = %s
            """, (athlete_id, user["id"]))
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="Access denied")
        elif user["role"] in ["coach", "head_coach"]:
            # Coaches can only access athletes from their branch
            if user["branch_id"] != branch_id:
                raise HTTPException(status_code=403, detail="You can't access athletes from other branches")

        # Get all attendances for that athlete in this month/year
        cursor.execute("""
            SELECT session_date, status, notes
            FROM attendance
            WHERE athlete_id = %s
              AND YEAR(session_date) = %s
              AND MONTH(session_date) = %s
            ORDER BY session_date ASC
        """, (athlete_id, year, month))
        records = cursor.fetchall()
        
        return {
            "athlete_id": athlete_id,
            "year": year,
            "month": month,
            "attendance": records
        }
    finally:
        cursor.close()
        conn.close()

@router.get("/athlete/{athlete_id}/stats")
def get_athlete_attendance_stats(
    athlete_id: int,
    year: int = Query(..., description="Year, e.g. 2024"),
    user=Depends(get_current_user),
):
    """Get attendance statistics for an athlete for a given year"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT u.branch_id FROM athletes a
            JOIN users u ON a.user_id = u.id
            WHERE a.id = %s
        """, (athlete_id,))
        info = cursor.fetchone()
        if not info:
            raise HTTPException(status_code=404, detail="Athlete not found")
        branch_id = info["branch_id"]

        # Check access permissions
        if user["role"] == "athlete":
            cursor.execute("""
                SELECT a.id FROM athletes a
                JOIN users u ON a.user_id = u.id
                WHERE a.id = %s AND u.id = %s
            """, (athlete_id, user["id"]))
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="Access denied")
        elif user["role"] in ["coach", "head_coach"]:
            if user["branch_id"] != branch_id:
                raise HTTPException(status_code=403, detail="You can't access athletes from other branches")

        # Get attendance statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_sessions,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_count,
                ROUND(
                    (SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) / COUNT(*)) * 100, 
                    2
                ) as attendance_rate
            FROM attendance
            WHERE athlete_id = %s
              AND YEAR(session_date) = %s
              AND status IS NOT NULL
        """, (athlete_id, year))
        stats = cursor.fetchone()
        
        # Get monthly breakdown
        cursor.execute("""
            SELECT 
                MONTH(session_date) as month,
                COUNT(*) as total_sessions,
                SUM(CASE WHEN status = 'present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as absent_count
            FROM attendance
            WHERE athlete_id = %s
              AND YEAR(session_date) = %s
              AND status IS NOT NULL
            GROUP BY MONTH(session_date)
            ORDER BY month
        """, (athlete_id, year))
        monthly_stats = cursor.fetchall()
        
        return {
            "athlete_id": athlete_id,
            "year": year,
            "overall_stats": stats,
            "monthly_breakdown": monthly_stats
        }
    finally:
        cursor.close()
        conn.close()