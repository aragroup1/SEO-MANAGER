import os
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from .state import active_sessions, AUTH_USERNAME, AUTH_PASSWORD, SESSION_EXPIRY_HOURS

router = APIRouter()


@router.post("/api/auth/login")
async def login(request: Request):
    data = await request.json()
    username = data.get("username", "")
    password = data.get("password", "")

    if not AUTH_PASSWORD:
        token = secrets.token_urlsafe(32)
        active_sessions[token] = datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)
        return {"success": True, "token": token, "message": "Auth disabled — no password set"}

    if username == AUTH_USERNAME and password == AUTH_PASSWORD:
        token = secrets.token_urlsafe(32)
        active_sessions[token] = datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)
        print(f"[Auth] Login successful for '{username}'")
        return {"success": True, "token": token}

    print(f"[Auth] Login FAILED for '{username}'")
    return JSONResponse(status_code=401, content={"success": False, "message": "Invalid username or password"})


@router.get("/api/auth/check")
async def check_auth(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""

    if not AUTH_PASSWORD:
        return {"authenticated": True, "auth_required": False}

    if token and token in active_sessions and active_sessions[token] > datetime.utcnow():
        return {"authenticated": True, "auth_required": True}

    return {"authenticated": False, "auth_required": True}


@router.post("/api/auth/logout")
async def logout(request: Request):
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "") if auth_header.startswith("Bearer ") else ""
    if token in active_sessions:
        del active_sessions[token]
    return {"success": True}
