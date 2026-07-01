from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)
