from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum
from data.tables import GenderEnum, SideEnum

class UserBase(BaseModel):
    is_doctor: bool =False

class UserLogin(BaseModel):
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Пароль пользователя (минимум 8 символов)"
    )

class UserRegister(UserBase):
    name: str
    email: EmailStr
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
    )
    city: str
    date_of_birth: datetime 
    gender: GenderEnum 
    weight: float = Field(
        ..., 
        ge=20, le=200, 
        description="Вес в кг"
    )
    height: float = Field(
        ..., 
        ge=80, le=210, 
        description="Рост в см"
    )
    have_injury: bool = Field(
        default=False, 
        description="Наличие травм"
    )
    shoe_size: float = Field(
        ..., 
        ge=10, le=50, 
        description="Размер обуви (RU)"
    )
    dominant_leg: SideEnum = Field(
        default=SideEnum.RIGHT, 
        description="Ведущая нога"
    )
    doctors: Optional[List[int]] = Field(description='Имя врача который наблюдает за вами(their public id)')
    @field_validator('email')
    def email_must_be_lowercase(cls, v):
        return v.lower()

    model_config = ConfigDict(from_attributes=True)
   
class DoctorRegister(UserBase):
    id: int
    name: str
    email: EmailStr
    password: str = Field(
        ...,
        min_length=6,
        max_length=100,
        description="Пароль (минимум 6 символов)"
    )
    gender: GenderEnum
    date_of_birth: datetime

    city: str
    workplace: str
    specialization: str
    license_id: str

    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str = Field(...)
    token_type: str = Field(default="bearer")

class UserResponse(BaseModel):
    id: int
    public_code: str
    name: str 
    email: str
    city: str
    date_of_birth: datetime
    gender: GenderEnum
    weight: float
    height: float
    have_injury: bool = False
    shoe_size: float
    dominant_leg: SideEnum = SideEnum.RIGHT
    doctors: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class DoctorResponse(BaseModel):
    id: int
    public_code: str
    name: str 
    email: str
    city: str
    date_of_birth: datetime
    gender: GenderEnum
    workplace: str
    specialization: str
    license_id: str
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)



