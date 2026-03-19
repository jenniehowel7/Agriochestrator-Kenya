from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from src.data.storage import AppStorage


app = FastAPI(title="AgriOrchestrator API", version="1.0.0")
storage = AppStorage()


class LoginRequest(BaseModel):
    username: str
    password: str


class FarmerProfileRequest(BaseModel):
    farmer_name: str
    county: str
    crop: str
    area_acres: float
    budget_kes: int
    phone: str | None = None


class SyncRequest(BaseModel):
    action: str
    payload: dict[str, Any]


def get_current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    user = storage.user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def require_roles(*roles: str):
    def _dep(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return _dep


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/login")
def login(payload: LoginRequest) -> dict[str, Any]:
    user = storage.authenticate(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {
        "token": user.token,
        "user": {"id": user.user_id, "username": user.username, "role": user.role},
    }


@app.get("/farmers")
def list_farmers(user: dict[str, Any] = Depends(get_current_user)) -> list[dict[str, Any]]:
    if user["role"] in {"admin", "officer"}:
        return storage.list_farmer_profiles()
    own = [p for p in storage.list_farmer_profiles() if p.get("owner_user_id") == user["id"]]
    return own


@app.post("/farmers")
def create_farmer(
    payload: FarmerProfileRequest,
    user: dict[str, Any] = Depends(require_roles("admin", "officer", "farmer")),
) -> dict[str, Any]:
    owner_id = user["id"] if user["role"] == "farmer" else None
    profile_id = storage.save_farmer_profile(payload.model_dump(), owner_user_id=owner_id)
    profile = storage.get_farmer_profile(profile_id)
    return {"message": "created", "profile": profile}


@app.put("/farmers/{profile_id}")
def update_farmer(
    profile_id: int,
    payload: FarmerProfileRequest,
    user: dict[str, Any] = Depends(require_roles("admin", "officer", "farmer")),
) -> dict[str, Any]:
    existing = storage.get_farmer_profile(profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Profile not found")
    if user["role"] == "farmer" and existing.get("owner_user_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Cannot edit another farmer profile")

    data = payload.model_dump()
    data["id"] = profile_id
    storage.save_farmer_profile(data, owner_user_id=existing.get("owner_user_id"))
    return {"message": "updated", "profile": storage.get_farmer_profile(profile_id)}


@app.post("/sync/enqueue")
def enqueue_sync(
    payload: SyncRequest,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    item_id = storage.enqueue_sync(payload.action, {**payload.payload, "user_id": user["id"]})
    return {"message": "queued", "id": item_id}


@app.get("/sync/pending")
def pending_sync(user: dict[str, Any] = Depends(require_roles("admin", "officer"))) -> list[dict[str, Any]]:
    return storage.list_pending_sync()


@app.post("/sync/flush")
def flush_sync(user: dict[str, Any] = Depends(require_roles("admin", "officer"))) -> dict[str, int]:
    return storage.flush_sync_queue()
