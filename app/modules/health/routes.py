from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def welcome():
    return {
        "status": True,
        "message": "Welcome to NexGenAI Chatbot 🚀"
    }