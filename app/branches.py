# app/branches.py - CLEAN VERSION with no conflicts

from fastapi import APIRouter, Depends, HTTPException
from app.database import get_connection
from app.deps import get_current_user

router = APIRouter()

# =================== PUBLIC ROUTES (NO AUTH REQUIRED) ===================
# These MUST come before parameterized routes like /{branch_id}

@router.get("/public")
def get_public_branches():
    """
    Get all branches for public use (registration form).
    No authentication required.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT id, name, address, phone, practice_days
            FROM branches
            ORDER BY name
        """)
        branches = cursor.fetchall()
        
        print(f"✅ Retrieved {len(branches)} branches for public access")
        return branches
        
    except Exception as e:
        print(f"❌ Error getting public branches: {e}")
        raise HTTPException(
            status_code=500, 
            detail="Failed to load branches"
        )
    finally:
        cursor.close()
        conn.close()

@router.get("/")
def list_branches():
    """Get all branches with basic info"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, address, phone, video_url, practice_days 
        FROM branches
        ORDER BY name
    """)
    branches = cursor.fetchall()
    cursor.close()
    conn.close()
    return branches

# =================== AUTHENTICATED ROUTES ===================

@router.get("/all")
def get_all_branches(user=Depends(get_current_user)):
    """Get all branches for management purposes"""
    if user["role"] not in ["head_coach", "admin"]:
        raise HTTPException(status_code=403, detail="Only head coaches and admins can view all branches")
    
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT id, name, address, phone, practice_days
        FROM branches
        ORDER BY name
    """)
    branches = cursor.fetchall()
    cursor.close()
    conn.close()
    return branches

# =================== DEPRECATED HEAD COACH ROUTES ===================
# These are kept for backward compatibility but should use /coach/set-active-branch instead

@router.post("/select-branch/{branch_id}")
def select_branch_for_head_coach(branch_id: int, user=Depends(get_current_user)):
    """
    DEPRECATED: Use /coach/set-active-branch/{branch_id} instead
    Kept for backward compatibility
    """
    if user["role"] != "head_coach":
        raise HTTPException(status_code=403, detail="Access denied - only head coaches")

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        print(f"⚠️ DEPRECATED ENDPOINT: Head coach {user['name']} using old branch selection")
        print(f"🔄 Recommend switching to /coach/set-active-branch/{branch_id}")
        
        # Verify branch exists
        cursor.execute("SELECT id, name FROM branches WHERE id = %s", (branch_id,))
        branch = cursor.fetchone()
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")

        # Update user's branch_id
        cursor.execute("UPDATE users SET branch_id = %s WHERE id = %s", (branch_id, user["id"]))
        conn.commit()

        return {
            "success": True,
            "message": f"Successfully switched to {branch['name']}",
            "new_active_branch_id": branch_id,
            "new_active_branch_name": branch['name'],
            "deprecated_warning": "This endpoint is deprecated. Use /coach/set-active-branch/{branch_id} instead."
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to select branch: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# =================== REMOVED CONFLICTING COACH ROUTES ===================
# These routes have been moved to /coach/ router to avoid conflicts:
# - /coach/assigned-branches -> moved to coach router
# - /coach/set-active-branch/{branch_id} -> moved to coach router

# =================== PARAMETERIZED ROUTES (MUST BE LAST) ===================
# These routes with path parameters should come AFTER specific routes

# ✅ FIXED: Update the get_branch endpoint in your branches.py

@router.get("/{branch_id}")
def get_branch(branch_id: int):
    """Get detailed information about a specific branch"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                id, 
                name, 
                address, 
                phone, 
                practice_days, 
                video_url,
                location_url,
                created_at
            FROM branches 
            WHERE id = %s
        """, (branch_id,))
        branch = cursor.fetchone()
        
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        
        print(f"✅ Retrieved branch: {branch['name']} (ID: {branch_id})")
        
        # ✅ FIXED: Return data directly under "data" key (not "branch")
        return {
            "success": True,
            "data": branch  # ✅ Changed from "branch": branch to "data": branch
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting branch {branch_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get branch: {str(e)}")
    finally:
        cursor.close()
        conn.close()

# ✅ ALSO ADD: Endpoint specifically for getting branch name quickly
@router.get("/{branch_id}/name")
def get_branch_name(branch_id: int):
    """Get just the branch name - optimized for quick lookups"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT id, name FROM branches WHERE id = %s", (branch_id,))
        branch = cursor.fetchone()
        
        if not branch:
            raise HTTPException(status_code=404, detail="Branch not found")
        
        print(f"✅ Retrieved branch name: {branch['name']} (ID: {branch_id})")
        
        return {
            "success": True,
            "data": {
                "id": branch['id'],
                "name": branch['name']
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error getting branch name {branch_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get branch name: {str(e)}")
    finally:
        cursor.close()
        conn.close()