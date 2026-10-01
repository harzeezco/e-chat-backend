from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterData(BaseModel):
    id: str
    email: EmailStr
    role: str


class RegisterResponse(BaseModel):
    success: bool
    message: str
    data: RegisterData | None
