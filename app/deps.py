# app/deps.py - FIXED VERSION (without non-existent columns)
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from app.config import settings
from app.database import get_db_cursor
import time

# Create HTTPBearer security scheme
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract and validate JWT token, return FRESH user info"""
    
    token = credentials.credentials
    
    # ✅ FIXED: Clean up token - remove extra quotes and whitespace
    if token:
        token = token.strip()
        if token.startswith('"') and token.endswith('"'):
            token = token[1:-1]  # Remove surrounding quotes
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=401, 
                detail="Invalid token: no user ID"
            )
        
    except JWTError as e:
        print(f"❌ JWT decode error: {e}")
        raise HTTPException(
            status_code=401, 
            detail="Could not validate token"
        )
    except Exception as e:
        print(f"❌ Unexpected error decoding JWT: {e}")
        raise HTTPException(
            status_code=401, 
            detail="Token validation failed"
        )
    
    # ✅ CRITICAL: Always get FRESH user data from database
    # ✅ FIXED: Only select columns that actually exist
    with get_db_cursor() as (cursor, connection):
        try:
            cursor.execute("""
                SELECT 
                    id, name, email, phone, role, branch_id, approved,
                    password_hash, created_at
                FROM users 
                WHERE id = %s
            """, (user_id,))
            
            user = cursor.fetchone()
            
            if not user:
                print(f"❌ User not found in database: {user_id}")
                raise HTTPException(
                    status_code=404, 
                    detail="User not found"
                )
            
            # Remove sensitive data before returning
            user_safe = dict(user)
            user_safe.pop('password_hash', None)
            
            print(f"✅ Fresh user data retrieved: {user_safe['name']} ({user_safe['email']})")
            return user_safe
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Database error in get_current_user: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Database error"
            )

# ✅ NEW: Add a function to get fresh user data without token validation
def get_fresh_user_data(user_id: int):
    """Get fresh user data from database - used for post-operation verification"""
    with get_db_cursor() as (cursor, connection):
        try:
            cursor.execute("""
                SELECT 
                    id, name, email, phone, role, branch_id, approved,
                    created_at
                FROM users 
                WHERE id = %s
            """, (user_id,))
            
            return cursor.fetchone()
            
        except Exception as e:
            print(f"❌ Error getting fresh user data: {e}")
            return None