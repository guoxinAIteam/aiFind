from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import datetime as _dt

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Simple in-memory user store for demo
USERS = {
    "admin": {"password": "admin123", "role": "admin", "name": "系统管理员"},
    "operator": {"password": "op123", "role": "operator", "name": "运维工程师"},
    "viewer": {"password": "view123", "role": "viewer", "name": "只读用户"},
}

SESSIONS = {}
AUDIT_LOG = []

ROLE_PERMISSIONS = {
    "admin": ["*"],
    "operator": ["flows:read", "flows:write", "flows:execute", "params:read", "params:write", "monitor:read", "knowledge:read", "knowledge:write", "manual:read", "skills:invoke"],
    "viewer": ["flows:read", "params:read", "monitor:read", "knowledge:read", "manual:read"],
}


class LoginReq(BaseModel):
    username: str
    password: str


class AuditEntry(BaseModel):
    timestamp: str
    user: str
    action: str
    resource: str
    detail: str = ""
    ip: str = ""


@router.post("/login")
def login(req: LoginReq, request: Request):
    user = USERS.get(req.username)
    if not user or user["password"] != req.password:
        raise HTTPException(401, "用户名或密码错误")
    import hashlib, os

    token = hashlib.sha256(f"{req.username}{os.urandom(16).hex()}".encode()).hexdigest()[:32]
    SESSIONS[token] = {
        "username": req.username,
        "role": user["role"],
        "name": user["name"],
        "created": _dt.datetime.utcnow().isoformat(),
    }
    AUDIT_LOG.append(
        {
            "timestamp": _dt.datetime.utcnow().isoformat(),
            "user": req.username,
            "action": "login",
            "resource": "auth",
            "ip": request.client.host if request.client else "",
        }
    )
    return {
        "token": token,
        "username": req.username,
        "role": user["role"],
        "name": user["name"],
        "permissions": ROLE_PERMISSIONS[user["role"]],
    }


@router.get("/me")
def get_me(token: Optional[str] = None):
    session = SESSIONS.get(token or "")
    if not session:
        return {"authenticated": False}
    return {"authenticated": True, **session, "permissions": ROLE_PERMISSIONS[session["role"]]}


@router.get("/audit")
def get_audit_log(limit: int = 50):
    return AUDIT_LOG[-limit:][::-1]


@router.post("/logout")
def logout(token: Optional[str] = None):
    if token and token in SESSIONS:
        del SESSIONS[token]
    return {"message": "已登出"}
