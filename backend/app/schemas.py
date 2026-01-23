from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
from enum import Enum
from data.tables import GenderEnum, SideEnum, ActivityType, SessionStatus

class UserBase(BaseModel):
    is_doctor: bool =False

class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=20)
    model_config = ConfigDict(from_attributes=True)

class UserRegister(UserBase):
    name: str
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    city: str
    date_of_birth: datetime 
    gender: GenderEnum 
    weight: float = Field(..., ge=20, le=200)
    height: float = Field(..., ge=80, le=210)
    have_injury: bool = Field(default=False)
    shoe_size: float = Field(..., ge=10, le=50)
    leg_length: float = Field(..., ge=10, le=150)
    dominant_leg: SideEnum = Field(default=SideEnum.RIGHT)
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
        min_length=8,
        max_length=100,
        description="Пароль (минимум 8 символов)"
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

class SessionCreate(BaseModel):
    is_baseline: bool = False
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Заметки пользователя о сессии"
    )

    model_config = ConfigDict(from_attributes=True)

class SessionStopResponse(BaseModel):
    session_id: int
    start_time: datetime
    end_time: datetime
    duration: float  # секунды
    status: SessionStatus
    model_config = ConfigDict(from_attributes=True)

class SessionListItem(BaseModel):
    session_id: int
    duration: float
    status: SessionStatus
    is_baseline: bool

    model_config = ConfigDict(from_attributes=True)
   
class SessionMetrics(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_count: int
    cadence: float
    avg_speed: float

    knee_angle_mean: float
    knee_angle_std: float
    knee_angle_max: float
    knee_angle_min: float
    knee_amplitude: float

    hip_angle_mean: float
    hip_angle_std: float
    hip_angle_max: float
    hip_angle_min: float
    hip_amplitude: float

    avg_stance_time: float
    avg_swing_time: float
    stance_swing_ratio: float

    gvi: float
    step_time_variability: float
    step_length_variability: float
    knee_angle_variability: float
    stance_time_variability: float

    avg_roll: float
    avg_yaw: float
    avg_pitch: float

class SessionResponse(BaseModel):
    session_id: int
    user_id: int
    status: SessionStatus
    is_baseline: bool
    is_processed: bool
    notes: Optional[str]
    metrics: Optional[SessionMetrics]
    
    model_config = ConfigDict(from_attributes=True)

class UploadResponse(BaseModel):
    status: str = Field(default="uploaded")
    session_id: int
    samples_count: int 
    duration: float
    message: str = Field(default="Data uploaded successfully. Processing started in background.")

class InjuryInfo(BaseModel):
    have_injury: bool = False
    body_part: List[str] = []
    side: Optional[str] = None
    injury_type: List[str] = []
    diagnosis_date: Optional[datetime] = None
    pain_level: int = Field(0, ge=0, le=10)
    is_active: bool = True

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    shoe_size: Optional[float] = None
    leg_length: Optional[float] = None
    dominant_leg: Optional[str] = None
    placed_leg: Optional[str] = None
    injury_info: Optional[InjuryInfo] = None

class UserResponse(UserBase):
    id: int
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True

class RhythmPace(BaseModel):
    step_count: int
    cadence: float
    avg_speed: float
    avg_peak_angular_velocity: float

class AngleMetrics(BaseModel):
    mean: float
    std: float
    max: float
    min: float
    amplitude: float

class Orientation(BaseModel):
    avg_roll: float
    avg_pitch: float
    avg_yaw: float

class JointMechanics(BaseModel):
    knee_angle: AngleMetrics
    hip_angle: AngleMetrics
    orientation: Orientation

class Variability(BaseModel):
    gvi: float
    step_time_variability: float
    knee_angle_variability: float
    stance_time_variability: float
    swing_time_variability: float
    stride_length_variability: float

class SymmetryPhases(BaseModel):
    avg_stance_time: float
    avg_swing_time: float
    stance_swing_ratio: float
    double_support_time: float
    avg_impact_force: float

class SessionMetrics(BaseModel):
    activity_type: List[str]
    notes: Optional[str] = None
    rhythm_pace: RhythmPace
    joint_mechanics: JointMechanics
    variability: Variability
    symmetry_phases: SymmetryPhases

class ReportCreate(BaseModel):
    user_id: int
    session_metrics: SessionMetrics

class ReportResponse(BaseModel):
    id: int
    user_id: int
    activity_type: Optional[List[str]]
    notes: Optional[str]
    
    protocol_reference: Optional[str]
    personalized_target: Optional[Dict[str, Any]]
    clinical_narrative: Optional[str]
    status: Optional[str]
    recommendations: Optional[str]
    overall_score: Optional[float]
    gvi_score: Optional[float]
    
    created_at: datetime
    
    class Config:
        from_attributes = True

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ChatRequest(BaseModel):
    user_id: int
    report_id: Optional[int] = None
    message: str

class ChatResponse(BaseModel):
    session_id: int
    response: str
    timestamp: datetime

class ChatSessionResponse(BaseModel):
    id: int
    user_id: int
    report_id: Optional[int]
    session_name: Optional[str]
    created_at: datetime
    is_active: bool
    
    class Config:
        from_attributes = True