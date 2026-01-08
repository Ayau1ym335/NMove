from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from data.tables import get_db, Users, Doctors
import os

load_dotenv() 
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 21600
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
app = FastAPI()

def verify_password(plain_p, hashed_p):
    return pwd_context.verify(plain_p, hashed_p)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({
        "exp": expire,  
        "iat": datetime.now(timezone.utc)
    })
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
async def get_current_user(token: str = Depends(oauth2_scheme),db: AsyncSession = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    result = await db.execute(select(Users).filter(Users.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        result = await db.execute(select(Doctors).filter(Doctors.email == email))
        user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str):
    result = await db.execute(select(Users).filter(Users.email == email))
    user = result.scalar_one_or_none()
    if not user:
        result = await db.execute(select(Doctors).filter(Doctors.email == email))
        user = result.scalar_one_or_none()
    if not user:
        return False
    if not verify_password(password, user.password):
        return False
        
    return user

#длина щиколотки до ног