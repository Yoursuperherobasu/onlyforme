"""
Store routes - Currently dummy implementations.
TODO: Migrate to a proper store backend in the future.
"""
from fastapi import APIRouter

router = APIRouter(tags=["Store"], prefix="/store")


@router.get("/check/api_key")
async def check_api_key():
    """Check if API key exists - dummy implementation returning OK."""
    return {"has_api_key": False, "is_valid": False}


@router.get("/check/")
async def check_store():
    """Check if store is available - dummy implementation returning OK."""
    return {"enabled": False}
