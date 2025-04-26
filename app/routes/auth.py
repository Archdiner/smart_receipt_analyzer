from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from app.services.supabase_client import supabase
from typing import Optional
import logging

router = APIRouter()
security = HTTPBearer()

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Dependency to get the current authenticated user.
    To be used with FastAPI's Depends.
    """
    try:
        # Get user from Supabase
        user_response = supabase.auth.get_user(credentials.credentials)
        if not user_response or not user_response.user:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user = user_response.user
        # Return a dictionary with the necessary user information
        return {
            "id": user.id,
            "email": user.email,
            "phone": user.phone,
            "created_at": user.created_at,
            "user_metadata": user.user_metadata,
            "app_metadata": user.app_metadata,
            "access_token": credentials.credentials
        }
    except Exception as e:
        logging.error(f"Authentication error: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.post("/register")
async def register(user: UserRegister):
    try:
        # Register user with Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": user.email,
            "password": user.password,
            "options": {
                "data": {
                    "first_name": user.first_name,
                    "last_name": user.last_name
                }
            }
        })
        
        if auth_response.user is None:
            raise HTTPException(status_code=400, detail="Registration failed")
        
        return {
            "message": "Registration successful. Please check your email for verification.",
            "user_id": auth_response.user.id
        }
        
    except Exception as e:
        logging.error(f"Registration error: {str(e)}")
        if "User already registered" in str(e):
            raise HTTPException(status_code=400, detail="Email already registered")
        raise HTTPException(status_code=500, detail="Registration failed")

@router.post("/login")
async def login(user: UserLogin):
    try:
        # Sign in user with Supabase Auth
        auth_response = supabase.auth.sign_in_with_password({
            "email": user.email,
            "password": user.password
        })
        
        if not auth_response.user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
            
        # Check if email is verified
        if not auth_response.user.email_confirmed_at:
            raise HTTPException(status_code=403, detail="Email not verified")
            
        return {
            "access_token": auth_response.session.access_token,
            "user": {
                "id": auth_response.user.id,
                "email": auth_response.user.email,
                "first_name": auth_response.user.user_metadata.get("first_name"),
                "last_name": auth_response.user.user_metadata.get("last_name")
            }
        }
        
    except Exception as e:
        logging.error(f"Login error: {str(e)}")
        if "Invalid login credentials" in str(e):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        raise HTTPException(status_code=500, detail="Login failed")

@router.get("/verify-email")
async def verify_email(token: str, request: Request):
    try:
        # Verify the token with Supabase
        type = request.query_params.get("type")
        if type != "email_verification":
            raise HTTPException(status_code=400, detail="Invalid verification type")
            
        # The token verification is handled automatically by Supabase
        # We just need to redirect to the frontend
        return {"url": "http://localhost:8501"}
        
    except Exception as e:
        logging.error(f"Email verification error: {str(e)}")
        raise HTTPException(status_code=500, detail="Email verification failed")

@router.get("/session")
async def check_session(token: str):
    try:
        # Verify the session token
        user = supabase.auth.get_user(token)
        return {"valid": True, "user": user.user}
    except Exception:
        return {"valid": False} 