# app/coach.py - RACE CONDITION FIX

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from app.deps import get_current_user
from app.database import get_db_cursor
from passlib.hash import bcrypt
import time

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

# 🔧 FIXED: Atomic branch switching with proper locking
@router.post("/set-active-branch/{branch_id}")
def set_coach_active_branch(branch_id: int, user=Depends(get_current_user)):
    """ATOMIC branch switching - prevents race conditions"""
    if user["role"] not in ["coach", "head_coach"]:
        raise HTTPException(status_code=403, detail="Only coaches and head coaches can set active branch")

    with get_db_cursor() as (cursor, connection):
        try:
            # 🔧 START TRANSACTION with row locking
            cursor.execute("START TRANSACTION")
            
            # 🔧 LOCK the user row to prevent concurrent updates
            cursor.execute("""
                SELECT id, name, branch_id, role 
                FROM users 
                WHERE id = %s 
                FOR UPDATE
            """, (user["id"],))
            
            current_user_db = cursor.fetchone()
            if not current_user_db:
                raise HTTPException(status_code=404, detail="User not found")
            
            # 🔧 Verify branch exists and get name
            cursor.execute("SELECT id, name FROM branches WHERE id = %s", (branch_id,))
            branch = cursor.fetchone()
            if not branch:
                raise HTTPException(status_code=404, detail="Branch not found")

            # 🔧 Permission check within transaction
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

            # 🔧 ATOMIC UPDATE with verification
            cursor.execute("""
                UPDATE users 
                SET branch_id = %s 
                WHERE id = %s AND branch_id = %s
            """, (branch_id, user["id"], current_user_db["branch_id"]))

            if cursor.rowcount == 0:
                # If no rows updated, maybe branch was already changed
                cursor.execute("SELECT branch_id FROM users WHERE id = %s", (user["id"],))
                current_branch = cursor.fetchone()
                if current_branch and current_branch["branch_id"] == branch_id:
                    # Already set to this branch
                    connection.commit()
                    return {
                        "success": True,
                        "message": f"Already set to {branch['name']}",
                        "new_active_branch_id": branch_id,
                        "new_active_branch_name": branch['name'],
                        "was_already_set": True
                    }
                else:
                    raise HTTPException(status_code=500, detail="Branch update failed")

            # 🔧 FINAL VERIFICATION within same transaction
            cursor.execute("SELECT branch_id FROM users WHERE id = %s", (user["id"],))
            verification = cursor.fetchone()
            
            if not verification or verification['branch_id'] != branch_id:
                raise HTTPException(
                    status_code=500, 
                    detail="Branch switch verification failed"
                )
            
            # 🔧 COMMIT only after verification
            connection.commit()

            return {
                "success": True,
                "message": f"Successfully switched to {branch['name']}",
                "new_active_branch_id": branch_id,
                "new_active_branch_name": branch['name'],
                "previous_branch_id": current_user_db['branch_id'],
                "user_role": user["role"],
                "verified": True,
                "atomic_update": True
            }

        except HTTPException:
            connection.rollback()
            raise
        except Exception as e:
            connection.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to set active branch: {str(e)}")

# 🔧 NEW: Force refresh user token endpoint
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

# 🔧 NEW: Get current branch with force refresh
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