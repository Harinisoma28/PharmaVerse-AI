from uuid import UUID

from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class CurrentUserResponse(BaseModel):
    id: UUID
    username: str
    # Seeded demo accounts use a reserved/special-use domain (e.g. *.local)
    # which Pydantic EmailStr rejects on output. The DB column is the source of
    # truth, so response serialization treats email as a plain string.
    email: str
    role: str
    organization: str | None = None