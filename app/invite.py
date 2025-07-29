# Add this to your FastAPI router (e.g., in users.py or a new invite.py file)

import secrets
import string
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_connection
from app.deps import get_current_user
from jose import jwt
from app.config import settings

router = APIRouter()

class CreateInviteLinkResponse(BaseModel):
    success: bool
    invite_token: str
    invite_url: str
    expires_at: str

class LoginWithInviteRequest(BaseModel):
    invite_token: str

def generate_invite_token(length=32):
    """Generate a secure random token for invite links"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

@router.post("/invite/create", response_model=CreateInviteLinkResponse)
def create_invite_link(user=Depends(get_current_user)):
    """Create a shareable invite link for the current user"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        print(f"🔗 Creating invite link for user {user['id']} ({user['name']})")
        
        # Generate unique token
        invite_token = generate_invite_token()
        
        # Set expiration time (24 hours from now)
        expires_at = datetime.now() + timedelta(hours=24)
        
        # Invalidate any existing unused invite links for this user
        cursor.execute("""
            UPDATE invite_links 
            SET invalidated_at = NOW() 
            WHERE user_id = %s AND used = 0 AND invalidated_at IS NULL
        """, (user["id"],))
        
        # Insert new invite link
        cursor.execute("""
            INSERT INTO invite_links (user_id, token, expires_at, used, created_at)
            VALUES (%s, %s, %s, 0, NOW())
        """, (user["id"], invite_token, expires_at))
        
        conn.commit()
        
        # Create the invite URL (adjust base URL as needed)
        base_url = "https://backendtest-production-acc4.up.railway.app"  # Replace with your actual domain
        invite_url = f"{base_url}/invite/{invite_token}"
        
        print(f"✅ Invite link created: {invite_url}")
        
        return CreateInviteLinkResponse(
            success=True,
            invite_token=invite_token,
            invite_url=invite_url,
            expires_at=expires_at.isoformat()
        )
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creating invite link: {e}")
        raise HTTPException(status_code=500, detail="Failed to create invite link")
    finally:
        cursor.close()
        conn.close()

@router.post("/invite/login")
def login_with_invite(data: LoginWithInviteRequest):
    """Login using an invite token"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        print(f"🔗 Attempting login with invite token: {data.invite_token}")
        
        # Clean up expired invite links
        cursor.execute("DELETE FROM invite_links WHERE expires_at < NOW()")
        
        # Find valid invite link
        cursor.execute("""
            SELECT il.*, u.id as user_id, u.name, u.email, u.phone, u.role, u.approved, u.branch_id
            FROM invite_links il
            JOIN users u ON il.user_id = u.id
            WHERE il.token = %s 
            AND il.used = 0 
            AND il.invalidated_at IS NULL 
            AND il.expires_at > NOW()
        """, (data.invite_token,))
        
        invite_record = cursor.fetchone()
        
        if not invite_record:
            print(f"❌ Invalid or expired invite token: {data.invite_token}")
            raise HTTPException(
                status_code=400,
                detail="Invalid or expired invite link"
            )
        
        # Mark invite link as used
        cursor.execute("""
            UPDATE invite_links 
            SET used = 1, used_at = NOW() 
            WHERE token = %s
        """, (data.invite_token,))
        
        conn.commit()
        
        # Create JWT token for the user
        token = jwt.encode(
            {"sub": str(invite_record["user_id"])},
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        
        print(f"✅ User {invite_record['name']} logged in via invite link")
        
        return {
            "success": True,
            "token": token,
            "user": {
                "id": invite_record["user_id"],
                "name": invite_record["name"],
                "email": invite_record["email"],
                "phone": invite_record["phone"],
                "role": invite_record["role"],
                "approved": bool(invite_record.get("approved", False)),
                "branch_id": invite_record["branch_id"],
            },
            "message": f"Successfully logged in as {invite_record['name']}"
        }
        
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error during invite login: {e}")
        raise HTTPException(status_code=500, detail="Failed to login with invite link")
    finally:
        cursor.close()
        conn.close()

@router.get("/invite/validate/{token}")
def validate_invite_token(token: str):
    """Validate an invite token without using it"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Clean up expired invite links
        cursor.execute("DELETE FROM invite_links WHERE expires_at < NOW()")
        
        # Check if invite link is valid
        cursor.execute("""
            SELECT il.expires_at, u.name, u.email, u.role
            FROM invite_links il
            JOIN users u ON il.user_id = u.id
            WHERE il.token = %s 
            AND il.used = 0 
            AND il.invalidated_at IS NULL 
            AND il.expires_at > NOW()
        """, (token,))
        
        invite_record = cursor.fetchone()
        
        if not invite_record:
            return {
                "valid": False,
                "message": "Invalid or expired invite link"
            }
        
        return {
            "valid": True,
            "user_name": invite_record["name"],
            "user_email": invite_record["email"],
            "user_role": invite_record["role"],
            "expires_at": invite_record["expires_at"].isoformat(),
            "message": f"Valid invite link for {invite_record['name']}"
        }
        
    except Exception as e:
        print(f"❌ Error validating invite token: {e}")
        raise HTTPException(status_code=500, detail="Failed to validate invite link")
    finally:
        cursor.close()
        conn.close()

@router.get("/invite/my-links")
def get_my_invite_links(user=Depends(get_current_user)):
    """Get all invite links created by the current user"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Clean up expired invite links
        cursor.execute("DELETE FROM invite_links WHERE expires_at < NOW()")
        
        # Get user's invite links
        cursor.execute("""
            SELECT token, expires_at, created_at, used, used_at, invalidated_at
            FROM invite_links
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 10
        """, (user["id"],))
        
        invite_links = cursor.fetchall()
        
        return {
            "success": True,
            "invite_links": invite_links
        }
        
    except Exception as e:
        print(f"❌ Error getting invite links: {e}")
        raise HTTPException(status_code=500, detail="Failed to get invite links")
    finally:
        cursor.close()
        conn.close()

@router.delete("/invite/{token}")
def invalidate_invite_link(token: str, user=Depends(get_current_user)):
    """Invalidate a specific invite link"""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Check if the invite link belongs to the current user
        cursor.execute("""
            SELECT id FROM invite_links 
            WHERE token = %s AND user_id = %s AND invalidated_at IS NULL
        """, (token, user["id"]))
        
        invite_link = cursor.fetchone()
        
        if not invite_link:
            raise HTTPException(
                status_code=404, 
                detail="Invite link not found or already invalidated"
            )
        
        # Invalidate the invite link
        cursor.execute("""
            UPDATE invite_links 
            SET invalidated_at = NOW() 
            WHERE token = %s
        """, (token,))
        
        conn.commit()
        
        return {
            "success": True,
            "message": "Invite link invalidated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        print(f"❌ Error invalidating invite link: {e}")
        raise HTTPException(status_code=500, detail="Failed to invalidate invite link")
    finally:
        cursor.close()
        conn.close()