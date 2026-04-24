from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from bson import ObjectId
from fastapi import HTTPException

from app.core.db import get_db
from app.core.security import create_access_token, hash_password, verify_password


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(email: str) -> Optional[dict]:
    return await get_db().users.find_one({"email": _normalize_email(email)})


async def get_user_by_id(user_id: str) -> Optional[dict]:
    try:
        oid = ObjectId(user_id)
    except Exception:
        return None
    return await get_db().users.find_one({"_id": oid})


async def create_user(full_name: str, email: str, password: str, role: str = "athlete") -> dict:
    email_normalized = _normalize_email(email)
    existing = await get_user_by_email(email_normalized)
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    doc = {
        "full_name": full_name.strip(),
        "email": email_normalized,
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.now(timezone.utc),
    }
    result = await get_db().users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


async def create_guest_user() -> dict:
    guest_email = f"guest-{uuid4().hex[:10]}@cricpose.local"
    guest_pw = uuid4().hex
    return await create_user(full_name="Guest Analyst", email=guest_email, password=guest_pw, role="guest")


async def authenticate(email: str, password: str) -> dict:
    user = await get_user_by_email(email)
    if not user or not verify_password(password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return user


def issue_token(user: dict) -> str:
    return create_access_token(str(user["_id"]), user["email"])
