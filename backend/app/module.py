from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Depends, status
from typing import List, Literal
import uvicorn
from datetime import datetime, timedelta
app = FastAPI()

class IMUSample(BaseModel):
    device_mac: str
    session_id: str
    device_pos: Literal['thigh', 'shin']
    timestamp: int
    accel_x: float
    accel_y: float
    accel_z: float
    gyro_x: float
    gyro_y: float
    gyro_z: float
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