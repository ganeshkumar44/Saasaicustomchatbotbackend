from fastapi import APIRouter

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.get("/")
def auth_welcome():
    return {
        "status": True,
        "message": "Auth Module Working"
    }