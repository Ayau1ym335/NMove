from sqlalchemy import (Column, Integer,String,CheckConstraint,
                        DateTime, Float, Boolean,  Enum as SQLEnum, text)
from datetime import datetime, timedelta
from sqlalchemy.orm import declarative_base
import enum
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = "postgresql+asyncpg://postgres:Ayaulym^2011@localhost:5433/stridex"
engine = create_async_engine(DATABASE_URL, echo=True)
session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with session() as sen:
        try:
            yield sen
        finally:
            await sen.close()

class GenderEnum(enum.Enum):
    MALE = 'male'
    FEMALE = 'female'

class StatusEnum(enum.Enum):
    THIGH = 'thigh'
    SHIN = 'shin'

class SideEnum(enum.Enum):
    LEFT = 'left'
    RIGHT = 'right'

class UserRoleEnum(enum.Enum):
    PATIENT = 'patient'
    DOCTOR = 'doctor'

class User(Base):
    __tablename__ = "user"
    id = Column(String(8), CheckConstraint('length(id) = 8'), index=True)
    name = Column(String, nullable=False, comment='Введите реальное ФИО')
    role = Column(SQLEnum(UserRoleEnum), nullable=False, default=UserRoleEnum.PATIENT)
    date_of_birth = Column(DateTime, nullable=False)
    #city enum
    city = Column(
        String(100),
        nullable=True,
        comment="Город проживания пользователя"
    )

    gender = Column(SQLEnum(GenderEnum), nullable=False)
    weight = Column(Float, nullable=False)
    height = Column(Float, nullable=False)

    shoe_size = Column(Float,nullable=False, comment="Размер обуви (RU)")
    has_flat_feet = Column(Boolean, default=False, comment="Наличие плоскостопия")
    #3d model
    pain_place = Column(SQLEnum(), )
    injury_history = Column(String(500), comment="Описание травм и стороны поражения")

    dominant_leg = Column(SQLEnum(SideEnum), default=SideEnum.RIGHT, comment="Ведущая нога")
    placed_leg = Column(SQLEnum(SideEnum), default=SideEnum.RIGHT, comment="Нога на которой расположен модуль")

    created_at = Column(DateTime,nullable=False, default=lambda: datetime.now())
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password = Column(
        String(12),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("email LIKE '%@%'", name="check_email_format"),
        CheckConstraint('height > 80 AND height < 210', name='check_height_range'),
        CheckConstraint('weight > 20 AND weight < 200', name='check_weight_range'),
    )

class Doctor(Base):
    __tablename__ = "doctor"
    id = Column(String(8), CheckConstraint('length(id) = 8'), index=True)
    name = Column(String, nullable=False, comment='Введите реальное ФИО')
    role = Column(SQLEnum(UserRoleEnum), nullable=False, default=UserRoleEnum.PATIENT)
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
    license_id = Column(Integer())
    gender = Column(SQLEnum(GenderEnum), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now())
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    password = Column(
        String(12),
        nullable=False,
    )
    __table_args__ = (
        CheckConstraint("email LIKE '%@%'", name="check_email_format"),
        CheckConstraint(
            'length(license_id) = 8',
            name='check_license_id_length'
        ),
    )

class RawData(Base):
    __tablename__ = "raw_data"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, index=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now())
    #thigh
    ta_x = Column(Float)
    ta_y = Column(Float)
    ta_z = Column(Float)
    tg_x = Column(Float)
    tg_y = Column(Float)
    tg_z = Column(Float)
    #shin
    sa_x = Column(Float)
    sa_y = Column(Float)
    sa_z = Column(Float)
    sg_x = Column(Float)
    sg_y = Column(Float)
    sg_z = Column(Float)
    expired_at = Column(DateTime, default=lambda: datetime.now() + timedelta(days=4))

class StepMetrics(Base):
    __tablename__ = "step_metrics"
    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, index=True, nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now())


async def hypertable(engine, base):
    async with engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

        # 2. Iterate through all tables defined in your code
        for table_name, table_object in base.metadata.tables.items():
            # Check if we tagged this table in the model definition
            hyper_info = table_object.info.get("is_hypertable")
            time_col = table_object.info.get("time_column")

            if hyper_info and time_col:
                print(f"Converting {table_name} to hypertable via column {time_col}...")

                # Execute the conversion
                await conn.execute(text(
                    f"SELECT create_hypertable('{table_name}', '{time_col}', if_not_exists => TRUE);"
                ))

    print("All hypertables processed.")