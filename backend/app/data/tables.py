#imports
from sqlalchemy import (Column, Integer,String,CheckConstraint,
                        DateTime, Float, Boolean, ForeignKey, JSON, Text, Enum as SQLEnum, text,
                        PrimaryKeyConstraint, Index)
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime, timezone
from sqlalchemy.orm import declarative_base, relationship
import enum
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import os
from dotenv import load_dotenv

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(
    DATABASE_URL,
    echo=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as sen:
        yield sen
       
#Enums
class GenderEnum(enum.Enum):
    MALE = 'male'
    FEMALE = 'female'

class SessionStatus(enum.Enum):
    RECORDING = 'recording'
    STOPPED = 'stopped'
    PROCESSING = 'processing'
    COMPLETED = 'completed'

class SideEnum(enum.Enum):
    LEFT = 'left'
    RIGHT = 'right'

class ActivityType(enum.Enum):
    STANDING = "standing"
    WALKING = "walking"
    STAIRS = "stairs"
    RUNNING = "running"
    JUMPING = "jumping"
    UNKNOWN = "unknown"

class ExerciseD(enum.Enum):
    EASY = 'easy'
    MEDIUM = 'medium'
    HARD = 'hard'

class BodyPart(enum.Enum):
    KNEE = 'knee'
    ANKLE = 'ankle'
    FEET = 'feet'
    HIP = 'hip'
    SHIN = 'shin'
    THIGH = 'thigh'

class InjuryType(enum.Enum):
    ACL_TEAR = 'acl_tear'
    ANKLE_SPRAIN = 'ankle_sprain'
    LIGAMENT_OTHER = 'ligament_other'
    FRACTURE = 'fracture'
    STRESS_FRACTURE = 'stress_fracture'
    ACHILLES_INJURY = 'achilles_injury'
    MUSCLE_STRAIN = 'muscle_strain'
    MENISCUS_TEAR = 'meniscus_tear'
    OSTEOARTHRITIS = 'osteoarthritis'
    FLATFOOT = 'flatfoot'
    POST_OP = 'post_operative'
    OTHER = 'other'

#Tables

class DoctorPatient(Base):
    __tablename__ = "doctor_patients"

    id = Column(Integer, primary_key=True)
    doctor_id = Column(Integer, ForeignKey("doctor.id"))
    patient_id = Column(Integer, ForeignKey("user.id"))

    access_granted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    access_revoked_at = Column(DateTime, nullable=True)
    notes = Column(String, nullable=True)  # Заметки врача о пациенте

class Users(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, autoincrement=True)
    public_code = Column(String(8), unique=True)
    devices = relationship("Devices", back_populates="user", cascade="all, delete-orphan")
    created_at = Column(DateTime,nullable=False, default=lambda: datetime.now(timezone.utc))
    name = Column(String, nullable=False, comment='Введите реальное ФИО')
    #city enum
    city = Column(
        String(100),
        nullable=True,
        comment="Город проживания пользователя"
    )
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password = Column(
        String(255),
        nullable=False,
    )
    doctors = relationship(
        "Doctors",
        secondary="doctor_patients",
        back_populates="users"
    )

    profile = relationship("Profiles", back_populates="user", uselist=False, cascade="all, delete-orphan")
    walking_sessions = relationship("WalkingSessions", back_populates="user", cascade="all, delete-orphan")
    progress_records = relationship("UserProgress", back_populates="user", cascade="all, delete-orphan")
    medical_reports = relationship("MedicalReport", back_populates="user", cascade="all, delete-orphan")
    injuries = relationship("Injury",back_populates="user",cascade="all, delete-orphan",uselist=False)


    __table_args__ = (
        CheckConstraint("email LIKE '%@%'", name="check_email_format"),
    )

class Profiles(Base):
    __tablename__ = 'profiles'
    id = Column(Integer, ForeignKey("user.id"), primary_key=True)
    date_of_birth = Column(DateTime, nullable=False)
    gender = Column(SQLEnum(GenderEnum), nullable=False)
    weight = Column(Float, nullable=False)
    height = Column(Float, nullable=False)

    have_injury = Column(Boolean, nullable=False, default=False)
    shoe_size = Column(Float, nullable=False, comment="Размер обуви (RU)")
    dominant_leg = Column(SQLEnum(SideEnum), default=SideEnum.RIGHT, comment="Ведущая нога")
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("Users", back_populates="profile")

    __table_args__ = (
        CheckConstraint('height > 80 AND height < 210', name='check_height_range'),
        CheckConstraint('weight > 20 AND weight < 200', name='check_weight_range'),
    )

class Injury(Base):
    __tablename__ = 'injuries'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id"), unique=True, nullable=False)
    body_part = Column(ARRAY(SQLEnum(BodyPart)), nullable=False)
    side = Column(SQLEnum(SideEnum), default=SideEnum.RIGHT)
    injury_type = Column(ARRAY(SQLEnum(InjuryType)), nullable=False)
    diagnosis_date = Column(DateTime, nullable=False)
    pain_level = Column(Integer, CheckConstraint(' pain_level >= 0 AND pain_level <= 10'), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    placed_leg = Column(SQLEnum(SideEnum), default=SideEnum.RIGHT, comment="Нога на которой расположен модуль")


class Doctors(Base):
    __tablename__ = "doctor"
    id = Column(Integer, primary_key=True, autoincrement=True)
    public_code = Column(String(8), unique=True, index=True)
    name = Column(String, nullable=False, comment='Введите реальное ФИО')
    date_of_birth = Column(DateTime, nullable=False)
    # city enum
    city = Column(
        String(100),
        nullable=True,
        comment="Город проживания пользователя"
    )
    workplace = Column(
        String(100),
        nullable=True,
        comment="Название организации или тип офиса"
    )
    specialization = Column(String(100), comment="Специализация")
    license_id = Column(String(12))
    gender = Column(SQLEnum(GenderEnum), nullable=False)
    created_at = Column(DateTime, nullable=False, default= lambda: datetime.now(timezone.utc))
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password = Column(
        String(255),
        nullable=False,
    )

    medical_reports = relationship("MedicalReport", back_populates="doctor")
    user = relationship(
        "Users",
        secondary="doctor_patients",
        back_populates="doctors"
    )

    __table_args__ = (
        CheckConstraint("email LIKE '%@%'", name="check_email_format"),
        CheckConstraint(
            'length(license_id) = 12',
            name='check_license_id_length'
        ),
    )

class Devices(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False)
    device_serial = Column(String(50), unique=True, nullable=False)
    placement = Column(Integer, nullable=False)
    side = Column(SQLEnum(SideEnum), nullable=False)

    user = relationship("Users", back_populates="devices")

class RawData(Base):
    __tablename__ = "raw_data"
    id = Column(Integer)
    __table_args__ = (
        PrimaryKeyConstraint('id', 'timestamp'),
        {
            "info": {
                "is_hypertable": True,
                "time_column": "timestamp"
            }
        }
    )
    session_id = Column(Integer, ForeignKey("walking_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    placement = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    a_x = Column(Float)
    a_y = Column(Float)
    a_z = Column(Float)
    g_x = Column(Float)
    g_y = Column(Float)
    g_z = Column(Float)

    session = relationship("WalkingSessions", back_populates="raw_data")

class WalkingSessions(Base):
    __tablename__ = "walking_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime)
    duration = Column(Float, comment="Длительность в секундах")

    status = Column(SQLEnum(SessionStatus), nullable=False, default=SessionStatus.STOPPED)
    activity_type = Column(SQLEnum(ActivityType), nullable=False, default=ActivityType.UNKNOWN )
    auto_detected = Column(Boolean, default=False, nullable=False)
    is_baseline = Column(Boolean, default=False, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True, comment="Заметки пользователя о сессии")

    #Basic metrics
    step_count = Column(Integer)
    cadence = Column(Float, comment="Каденс (шагов/мин)")
    avg_speed = Column(Float, comment="Средняя скорость (м/с)")

    # Joint Angles - Knee
    knee_angle_mean = Column(Float)
    knee_angle_std = Column(Float)
    knee_angle_max = Column(Float)
    knee_angle_min = Column(Float)
    knee_amplitude = Column(Float, comment="Размах движения колена")

    # Joint Angles - Hip
    hip_angle_mean = Column(Float)
    hip_angle_std = Column(Float)
    hip_angle_max = Column(Float)
    hip_angle_min = Column(Float)
    hip_amplitude = Column(Float)

    # Temporal Metrics
    avg_stance_time = Column(Float, comment="Среднее время опоры")
    avg_swing_time = Column(Float, comment="Среднее время маха")
    stance_swing_ratio = Column(Float)

    # Variability
    gvi = Column(Float, comment="Gait Variability Index (%)")
    step_time_variability = Column(Float, comment="CV% времени шага")
    knee_angle_variability = Column(Float, comment="CV% угла колена")
    stance_time_variability = Column(Float, comment="CV% времени опоры")

    # Orientation (avg from Madgwick)
    avg_roll = Column(Float)
    avg_pitch = Column(Float)
    avg_yaw = Column(Float)

    user = relationship("Users", back_populates="walking_sessions")
    raw_data = relationship("RawData", back_populates="session", cascade="all, delete-orphan")
    step_metrics = relationship("StepMetrics", back_populates="session", cascade="all, delete-orphan")

class StepMetrics(Base):
    __tablename__ = "step_metrics"
    __table_args__ = (
        PrimaryKeyConstraint('id', 'timestamp'),
        {
            "info": {
                "is_hypertable": True,
                "time_column": "timestamp"
            }
        }
    )
    id = Column(Integer)
    session_id = Column(Integer, ForeignKey("walking_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    timestamp = Column(DateTime,default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    step_number = Column(Integer, comment="Номер шага в сессии")

    roll = Column(Float, comment="Крен (градусы)")
    pitch = Column(Float, comment="Тангаж (градусы)")
    yaw = Column(Float, comment="Рыскание (градусы)")

    knee_angle = Column(Float, comment="Угол колена (градусы)")
    hip_angle = Column(Float, comment="Угол бедра (градусы)")
    ankle_angle = Column(Float, comment="Угол голеностопа (градусы)")

    # Temporal Metrics
    stance_time = Column(Float, comment="Время опоры (сек)")
    swing_time = Column(Float, comment="Время маха (сек)")
    step_time = Column(Float, comment="Время шага (сек)")

    session = relationship("WalkingSessions", back_populates="step_metrics")
    device = relationship("Devices")

class UserProgress(Base):
    __tablename__ = "user_progress"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)

    # Time Period
    period_type = Column(String(20), nullable=False, comment="week/month")
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)

    # Aggregated Stats
    total_sessions = Column(Integer)
    total_steps = Column(Integer)

    # Average Metrics
    avg_cadence = Column(Float)
    avg_gvi = Column(Float)
    avg_knee_angle = Column(Float)
    avg_hip_angle = Column(Float)
    avg_speed = Column(Float)

    # Comparison with Baseline
    cadence_vs_baseline = Column(Float, comment="% изменения от baseline")
    gvi_vs_baseline = Column(Float)
    knee_amplitude_vs_baseline = Column(Float)

    # Trend Analysis
    trend = Column(String(20), comment="improving/stable/declining")
    improvement_score = Column(Float, comment="0-100 общий балл улучшения")

    # Relationship
    user = relationship("Users", back_populates="progress_records")

    __table_args__ = (
        CheckConstraint("period_type IN ('week', 'month')", name="check_period_type"),
    )

class Exercises(Base):
        __tablename__ = "exercises"

        id = Column(Integer, primary_key=True, autoincrement=True)

        # Basic Info
        name = Column(String(255), nullable=False)
        description = Column(Text)
        instructions = Column(Text, comment="Пошаговая инструкция")

        # Media
        video_url = Column(String(500))
        thumbnail_url = Column(String(500))
        duration = Column(Integer, comment="Длительность (сек)")

        # Categorization
        category = Column(String(50), comment="balance/strength/flexibility/gait_training")
        target_area = Column(String(50), comment="knee/hip/ankle/general")
        difficulty = Column(SQLEnum(ExerciseD), default=ExerciseD.EASY)

        # For which issues
        addresses_issues = Column(JSON, comment='["low_cadence", "high_gvi", ...]')

        # Recommendations
        recommended_sets = Column(Integer, default=3)
        recommended_reps = Column(Integer, default=10)
        rest_time = Column(Integer, comment="Отдых между подходами (сек)")

class MedicalReport(Base):
    __tablename__ = "medical_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("user.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id = Column(Integer, ForeignKey("doctor.id", ondelete="SET NULL"), nullable=True)
    report_start_date = Column(DateTime, nullable=False)
    report_end_date = Column(DateTime, nullable=False)
    session_ids = Column(JSON, comment='[session_id, session_id, ...]')
    pdf_filename = Column(String(255))
    pdf_url = Column(String(500), comment="S3/local path")
    pdf_size = Column(Integer, comment="Размер в байтах")
    summary = Column(JSON, comment='{"avg_cadence": 115, "improvement": "+12%", ...}')
    patient = relationship("Users", back_populates="medical_reports")
    doctor = relationship("Doctors")


async def init_database():
    """Initialize all tables including TimescaleDB hypertables"""
    async with engine.connect() as conn:
        async with conn.begin():
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
            await conn.run_sync(Base.metadata.create_all)
            await convert_to_hypertables(conn)
            await create_indexes(conn)
            await setup_retention_policies(conn)

async def convert_to_hypertables(conn):
    """Convert tables to TimescaleDB hypertables based on metadata"""
    for table_name, table_object in Base.metadata.tables.items():
        is_hypertable = table_object.info.get("is_hypertable", False)
        time_col = table_object.info.get("time_column")
        if is_hypertable and time_col:
            try:
                await conn.execute(text(
                    f"SELECT create_hypertable('{table_name}', '{time_col}', "
                    f"if_not_exists => TRUE, migrate_data => TRUE);"
                ))
                print(f" {table_name} hypertable")
            except Exception as e:
                print(f" {table_name} warning: {e}")

async def create_indexes(conn):
    """Create additional indexes for performance"""
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_user_sessions_date ON walking_sessions(user_id, start_time DESC);",
        "CREATE INDEX IF NOT EXISTS idx_progress_period ON user_progress(user_id, period_type, period_start DESC);",
        "CREATE INDEX IF NOT EXISTS idx_raw_data_session_time ON raw_data(session_id, timestamp DESC);",
        "CREATE INDEX IF NOT EXISTS idx_step_metrics_user ON step_metrics(session_id, timestamp DESC);"
    ]

    for index_sql in indexes:
        try:
            await conn.execute(text(index_sql))
            print(f" {index_sql.split('idx_')[1].split(' ')[0]}")
        except Exception as e:
            print(f"  {e}")

async def setup_retention_policies(conn):
    """Setup TimescaleDB retention policies"""
    try:
        await conn.execute(text(
            "SELECT add_retention_policy('raw_data', INTERVAL '3 days', "
            "if_not_exists => TRUE);"
        ))

        await conn.execute(text(
            "SELECT add_retention_policy('step_metrics', INTERVAL '7 days', "
            "if_not_exists => TRUE);"
        ))

        await conn.execute(text(
            "SELECT add_retention_policy('walking_sessions', INTERVAL '30 days', "
            "if_not_exists => TRUE);"
        ))
    except Exception as e:
        print(f"Retention policy warning: {e}")


async def drop_all_tables():
    async with engine.connect() as conn:
        async with conn.begin():
            await conn.run_sync(Base.metadata.drop_all)

async def main():
    await init_database()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())