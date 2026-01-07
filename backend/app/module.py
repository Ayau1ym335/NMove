from fastapi import FastAPI, HTTPException, Depends, status
from typing import List
import uvicorn
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from data.tables import init_database
from routers import auth_r
from schemas import IMUSample
from contextlib import asynccontextmanager 
app = FastAPI(
    title="Gait Analysis API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database() 
    yield

app.include_router(auth_r.router)

@app.get("/")
async def root():
    return {
        "message": "Gait Analysis API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.post('/ingest', status_code=200)
async def ingest(sample: List[IMUSample]):
    if not sample:
        raise HTTPException(status_code=400, detail="Sample is empty")

    thigh_count = sum(1 for s in sample if s.device_pos == 'thigh')
    shin_count = sum(1 for s in sample if s.device_pos == 'shin')
    print(f' shin_count: {shin_count}, thigh_count: {thigh_count}')
    return {'received': len(sample), 'status' : 'success'}


if __name__ == "__main__":
    uvicorn.run("module:app", port=8000, reload=True)