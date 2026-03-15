"""API v1 router — aggregates all endpoint routers."""
from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth, organizations, users, templates, 
    certificates, batches, verify, fonts
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(organizations.router)
api_router.include_router(users.router)
api_router.include_router(templates.router)
api_router.include_router(certificates.router)
api_router.include_router(batches.router)
api_router.include_router(verify.router)
api_router.include_router(fonts.router)
