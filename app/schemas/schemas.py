from typing import List, Optional

from pydantic import BaseModel, EmailStr, constr
from enum import Enum


# ========== USER SCHEMAS ==========

class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserRole(str, Enum):
    user = "user"
    agency = "agency"
    admin = "admin"

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: constr(min_length=6)
    role: UserRole = UserRole.user  # Optional, defaults to 'user'

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_verified: bool
    role: UserRole

    class Config:
        orm_mode = True

    class Config:
        orm_mode = True

class UpdateProfile(BaseModel):
    username: Optional[str]
    email: Optional[EmailStr]
    agency_name: Optional[str]
    agency_address: Optional[str]

# ========== AUTH SCHEMAS ==========

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    id: Optional[int] = None


class LoginSchema(BaseModel):
    email: EmailStr
    password: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


# ========== PROPERTY IMAGE SCHEMAS ==========

class PropertyImageOut(BaseModel):
    id: int
    url: str

    class Config:
        orm_mode = True


# ========== PROPERTY SCHEMAS ==========

class PropertyBase(BaseModel):
    title: str
    description: str
    price: int
    location: str

class BecomeAgency(BaseModel):
    agency_name: str
    agency_address: str


class PropertyCreate(PropertyBase):
    image_urls: List[str]


class PropertyOut(PropertyBase):
    id: int
    owner_id: int
    images: List[PropertyImageOut] = []

    class Config:
        orm_mode = True


class PropertyUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    location: Optional[str] = None



# ========== MESSAGE SCHEMAS ==========

class MessageBase(BaseModel):
    content: str


class MessageCreate(MessageBase):
    receiver_id: int
    property_id: int


class MessageOut(MessageBase):
    id: int
    sender_id: int
    receiver_id: int
    property_id: int

    class Config:
        orm_mode = True
