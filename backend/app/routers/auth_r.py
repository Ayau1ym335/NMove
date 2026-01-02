from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from data.tables import get_db, Users, Doctors, Profiles
from schemas import UserLogin, UserBase,DoctorRegister, UserRegister, Token, UserResponse, DoctorResponse
from app.auth import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    authenticate_user,
    get_current_user
)
from sqlalchemy import select

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
    responses={
        401: {"description": "Unauthorized"},
        404: {"description": "Not found"}
    }
)

@router.post("/register/patient", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Users).where(Users.email == user_data.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    #checking if doctors exist
    valid_doctors = []
    if user_data.doctors:
        result = await db.execute(select(Doctors).where(Doctors.public_code.in_(user_data.doctors)))
        existing_doctors = result.scalars().all()
        if len(existing_doctors) != len(user_data.doctors):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor(s) IDs are invalid"
            )
        valid_doctors = [doctor.public_code for doctor in existing_doctors]

    hashed_password = get_password_hash(user_data.password)
    new_user = Users(
        email=user_data.email,
        password=hashed_password,
        name=user_data.name,
        city=user_data.city,
        doctors=valid_doctors
    )

    db.add(new_user)
    await db.flush() 
    new_user.public_code = f"{new_user.id:08d}"
    profile = Profiles(
        public_code=new_user.public_code,
        date_of_birth=user_data.date_of_birth,
        gender=user_data.gender,
        height=user_data.height,
        weight=user_data.weight,
        have_injury=user_data.have_injury,
        shoe_size=user_data.shoe_size,
        dominant_leg=user_data.dominant_leg
    )
  
    db.add(profile)
    #sending request to the doctor(st. pending)  [Later]

    try:
        await db.commit()
        await db.refresh(new_user)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Database commit failed")
    return new_user 

@router.post("/register/doctor", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED)
async def register_d(data: DoctorRegister, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Doctors).where(Doctors.email == data.email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )
    hashed_password = get_password_hash(data.password)
    new_doctor = Doctors(
        email=data.email,
        password=hashed_password,
        name=data.name,
        date_of_birth=data.date_of_birth,
        gender=data.gender,
        city=data.city,
        specialization=data.specialization,
        license_id=data.license_id,
        workplace=data.workplace
    )
    db.add(new_doctor)
    try:
        await db.flush() 
        new_doctor.public_code = f"D{new_doctor.id:08d}"
        await db.commit()
        await db.refresh(new_doctor)
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create user profile")
    return new_doctor


@router.post("/login-secure",response_model=Token,status_code=status.HTTP_200_OK,)
async def login_secure(credentials: UserLogin,db: AsyncSession = Depends(get_db)):
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    token_data = {
        "sub": user.email,
        "user_id": user.id
    }
    access_token = create_access_token(data=token_data)
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
    

