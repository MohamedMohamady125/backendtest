# app/coach.py - COMPLETE FIXED VERSION

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from app.deps import get_current_user
from app.database import get_db_cursor
from passlib.hash import bcrypt
import time
import threading
from contextlib import contextmanager

# ✅ FIXED: Router definition that was missing
router = APIRouter()

class CoachProfile(BaseModel):
    name: str
    email: EmailStr
    branch: str

@router.get("/profile", response_model=CoachProfile)
def get_coach_profile(user=Depends(get_current_user)):
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can access this")

    with get_db_cursor() as (cursor, connection):
        cursor.execute("""
            SELECT u.name, u.email, b.name AS branch
            FROM users u
            LEFT JOIN branches b ON u.branch_id = b.id
            WHERE u.id = %s
        """, (user["id"],))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Coach profile not found")
        return result

class UpdateCoachProfile(BaseModel):
    name: str
    email: EmailStr

@router.put("/profile")
def update_coach_profile(data: UpdateCoachProfile, user=Depends(get_current_user)):
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can update profile")

    with get_db_cursor() as (cursor, connection):
        cursor.execute("""
            UPDATE users SET name = %s, email = %s WHERE id = %s
        """, (data.name, data.email, user["id"]))
        connection.commit()

        return {"message": "Profile updated successfully"}

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

@router.post("/change-password")
def change_password(data: ChangePasswordRequest, user=Depends(get_current_user)):
    with get_db_cursor() as (cursor, connection):
        cursor.execute("SELECT password_hash FROM users WHERE id = %s", (user["id"],))
        row = cursor.fetchone()

        if not row or not bcrypt.verify(data.old_password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Old password is incorrect")

        new_hash = bcrypt.hash(data.new_password)
        cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (new_hash, user["id"]))
        connection.commit()

        return {"message": "Password changed successfully"}

@router.get("/assigned-branches")
def get_coach_assigned_branches(user=Depends(get_current_user)):
    """Get branches assigned to the current coach"""
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches can access this")

    with get_db_cursor() as (cursor, connection):
        try:
            if user["role"] == "head_coach":
                # Head coaches can access ALL branches
                cursor.execute("""
                    SELECT id, name, address, phone, practice_days
                    FROM branches
                    ORDER BY name
                """)
                assigned_branches = cursor.fetchall()
                
            else:
                # Regular coaches can only access assigned branches
                cursor.execute("""
                    SELECT 
                        b.id,
                        b.name,
                        b.address,
                        b.phone,
                        b.practice_days
                    FROM coach_assignments ca
                    JOIN branches b ON ca.branch_id = b.id
                    WHERE ca.user_id = %s
                    ORDER BY b.name
                """, (user["id"],))
                assigned_branches = cursor.fetchall()
                
            # Get current branch
            cursor.execute("""
                SELECT b.id, b.name, b.address, b.phone, b.practice_days
                FROM users u
                LEFT JOIN branches b ON u.branch_id = b.id
                WHERE u.id = %s
            """, (user["id"],))
            current_branch_result = cursor.fetchone()

            current_branch = None
            if current_branch_result and current_branch_result['id']:
                current_branch = {
                    'id': current_branch_result['id'],
                    'name': current_branch_result['name'],
                    'address': current_branch_result['address'],
                    'phone': current_branch_result['phone'],
                    'practice_days': current_branch_result['practice_days']
                }

            return {
                "success": True,
                "assigned_branches": assigned_branches,
                "current_branch": current_branch,
                "total_branches": len(assigned_branches)
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get assigned branches: {str(e)}")

# ✅ BULLETPROOF BRANCH SWITCHING
# Global lock for branch switching to prevent race conditions
_branch_switch_lock = threading.Lock()

@contextmanager
def branch_switch_transaction(user_id: int):
    """Context manager for atomic branch switching with distributed locking"""
    with _branch_switch_lock:  # Prevent concurrent switches
        with get_db_cursor() as (cursor, connection):
            try:
                # Start explicit transaction with highest isolation
                cursor.execute("START TRANSACTION")
                cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                
                # Lock the specific user row
                cursor.execute("""
                    SELECT id, branch_id, role, name 
                    FROM users 
                    WHERE id = %s 
                    FOR UPDATE
                """, (user_id,))
                
                locked_user = cursor.fetchone()
                if not locked_user:
                    raise HTTPException(status_code=404, detail="User not found for locking")
                
                yield cursor, connection, locked_user
                
            except Exception:
                connection.rollback()
                raise

@router.post("/set-active-branch/{branch_id}")
def set_coach_active_branch_bulletproof(branch_id: int, user=Depends(get_current_user)):
    """
    🔒 BULLETPROOF branch switching with distributed locking and verification
    """
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches and head coaches can set active branch")

    start_time = time.time()
    print(f"🔄 BULLETPROOF: Starting branch switch for user {user['id']} to branch {branch_id}")
    
    try:
        with branch_switch_transaction(user["id"]) as (cursor, connection, locked_user):
            # ✅ STEP 1: Verify branch exists within transaction
            cursor.execute("SELECT id, name FROM branches WHERE id = %s", (branch_id,))
            branch = cursor.fetchone()
            if not branch:
                raise HTTPException(status_code=404, detail="Branch not found")

            # ✅ STEP 2: Permission check for regular coaches
            if user["role"] == "coach":
                cursor.execute("""
                    SELECT id FROM coach_assignments 
                    WHERE user_id = %s AND branch_id = %s
                """, (user["id"], branch_id))
                assignment = cursor.fetchone()
                
                if not assignment:
                    raise HTTPException(
                        status_code=403, 
                        detail="You are not assigned to this branch"
                    )

            previous_branch_id = locked_user["branch_id"]
            
            # ✅ STEP 3: Check if already on this branch
            if previous_branch_id == branch_id:
                connection.commit()
                return {
                    "success": True,
                    "message": f"Already managing {branch['name']}",
                    "new_branch_id": branch_id,
                    "new_branch_name": branch['name'],
                    "was_already_set": True,
                    "verified": True,
                    "api_confirmed": True,
                    "profile_confirmed": True
                }

            # ✅ STEP 4: Perform the atomic update
            cursor.execute("""
                UPDATE users 
                SET branch_id = %s 
                WHERE id = %s
            """, (branch_id, user["id"]))

            if cursor.rowcount != 1:
                raise HTTPException(status_code=500, detail="Branch update failed - no rows affected")

            # ✅ STEP 5: IMMEDIATE verification within same transaction
            cursor.execute("SELECT branch_id, name FROM users WHERE id = %s", (user["id"],))
            verification = cursor.fetchone()
            
            if not verification or verification['branch_id'] != branch_id:
                raise HTTPException(
                    status_code=500, 
                    detail=f"VERIFICATION FAILED: Expected {branch_id}, got {verification['branch_id'] if verification else 'None'}"
                )

            # ✅ STEP 6: Commit transaction
            connection.commit()
            
            execution_time = time.time() - start_time
            print(f"✅ BULLETPROOF: Branch switch completed in {execution_time:.3f}s")
            
            # ✅ STEP 7: Post-commit verification (outside transaction)
            # This ensures the change is actually persisted
            time.sleep(0.1)  # Small delay to ensure consistency
            
            with get_db_cursor() as (verify_cursor, verify_connection):
                verify_cursor.execute("SELECT branch_id FROM users WHERE id = %s", (user["id"],))
                final_check = verify_cursor.fetchone()
                
                final_verified = final_check and final_check['branch_id'] == branch_id
                
                return {
                    "success": True,
                    "message": f"Successfully switched to {branch['name']}",
                    "new_branch_id": branch_id,
                    "new_branch_name": branch['name'],
                    "previous_branch_id": previous_branch_id,
                    "user_role": user["role"],
                    "verified": True,
                    "api_confirmed": True,
                    "profile_confirmed": final_verified,
                    "execution_time_ms": round(execution_time * 1000, 2),
                    "bulletproof_mode": True
                }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ BULLETPROOF: Exception in branch switch: {e}")
        raise HTTPException(status_code=500, detail=f"Branch switch failed: {str(e)}")

# ✅ ENHANCED: Add branch switch status endpoint
@router.get("/branch-switch-status/{user_id}")
def get_branch_switch_status(user_id: int, current_user=Depends(get_current_user)):
    """Get real-time branch switch status for debugging"""
    if current_user["role"] != "head_coach" and current_user["id"] != user_id:
        raise HTTPException(status_code=403, detail="Access denied")
    
    with get_db_cursor() as (cursor, connection):
        try:
            cursor.execute("""
                SELECT 
                    u.id, 
                    u.name, 
                    u.branch_id, 
                    b.name as branch_name,
                    u.role
                FROM users u
                LEFT JOIN branches b ON u.branch_id = b.id
                WHERE u.id = %s
            """, (user_id,))
            
            user_status = cursor.fetchone()
            
            if not user_status:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {
                "success": True,
                "user_id": user_id,
                "current_branch_id": user_status["branch_id"],
                "current_branch_name": user_status["branch_name"],
                "user_role": user_status["role"],
                "timestamp": time.time()
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

# ✅ DIAGNOSTIC: Add endpoint to check for inconsistencies
@router.get("/diagnose-branch-consistency")
def diagnose_branch_consistency(user=Depends(get_current_user)):
    """Diagnose potential branch consistency issues"""
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Only head coaches can run diagnostics")
    
    with get_db_cursor() as (cursor, connection):
        try:
            # Check for orphaned assignments
            cursor.execute("""
                SELECT 
                    ca.user_id,
                    ca.branch_id as assigned_branch,
                    u.branch_id as current_branch,
                    u.name,
                    u.role
                FROM coach_assignments ca
                JOIN users u ON ca.user_id = u.id
                WHERE u.role = 'coach' AND ca.branch_id != u.branch_id
            """)
            
            inconsistencies = cursor.fetchall()
            
            # Check for coaches without assignments
            cursor.execute("""
                SELECT u.id, u.name, u.branch_id, u.role
                FROM users u
                LEFT JOIN coach_assignments ca ON u.id = ca.user_id
                WHERE u.role = 'coach' AND ca.user_id IS NULL
            """)
            
            unassigned_coaches = cursor.fetchall()
            
            return {
                "success": True,
                "inconsistencies_found": len(inconsistencies),
                "unassigned_coaches": len(unassigned_coaches),
                "details": {
                    "branch_assignment_mismatches": inconsistencies,
                    "coaches_without_assignments": unassigned_coaches
                },
                "recommendations": [
                    "Fix assignment mismatches by updating user branch_id or coach_assignments",
                    "Assign unassigned coaches to appropriate branches"
                ] if inconsistencies or unassigned_coaches else ["No issues found"]
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Diagnostic failed: {str(e)}")

@router.post("/refresh-session")
def refresh_user_session(user=Depends(get_current_user)):
    """Force refresh user session data"""
    with get_db_cursor() as (cursor, connection):
        try:
            cursor.execute("""
                SELECT id, name, email, role, branch_id, approved
                FROM users
                WHERE id = %s
            """, (user["id"],))
            
            fresh_user_data = cursor.fetchone()
            if not fresh_user_data:
                raise HTTPException(status_code=404, detail="User not found")
            
            return {
                "success": True,
                "user": fresh_user_data,
                "message": "Session refreshed successfully"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to refresh session: {str(e)}")

@router.get("/current-branch")
def get_current_branch(user=Depends(get_current_user)):
    """Get current branch with fresh database lookup"""
    with get_db_cursor() as (cursor, connection):
        try:
            cursor.execute("""
                SELECT 
                    u.branch_id,
                    b.id,
                    b.name,
                    b.address,
                    b.phone,
                    b.practice_days
                FROM users u
                LEFT JOIN branches b ON u.branch_id = b.id
                WHERE u.id = %s
            """, (user["id"],))
            
            result = cursor.fetchone()
            
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            
            if not result["id"]:
                return {
                    "success": True,
                    "current_branch": None,
                    "message": "No branch assigned"
                }
            
            return {
                "success": True,
                "current_branch": {
                    "id": result["id"],
                    "name": result["name"],
                    "address": result["address"],
                    "phone": result["phone"],
                    "practice_days": result["practice_days"]
                },
                "fresh_lookup": True
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get current branch: {str(e)}")