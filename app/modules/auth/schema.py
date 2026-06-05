from pydantic import BaseModel


class AuthResponse(BaseModel):
    status: bool
    message: str