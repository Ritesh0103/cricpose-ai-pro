from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/")
async def root() -> dict:
    return {"service": "CricPose AI Pro", "status": "ok"}


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}
