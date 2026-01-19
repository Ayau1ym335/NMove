# routers/sessions_r.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from typing import List, Optional
from datetime import datetime, timezone
from app.data.tables import get_db, WalkingSessions, Users, ActivityType, SessionStatus, Devices
from auth import get_current_user
from schemas import (
    SessionCreate,
    SessionStopResponse,
    SessionMetrics,
    SessionListItem,
    SessionResponse,
    RawDataUpload
)
from fastapi import UploadFile, File
import numpy as np
from sqlalchemy import update
from sqlalchemy.orm import selectinload
from d_processing.raw_process import GaitAnalysisOrchestrator
from d_processing.dclass import Metadata as SessionMetadata
from d_processing.step_metrics import calculate_step_metrics
from d_processing.unpacking import unpack_bin


router = APIRouter(
    prefix="/api/sessions",
    tags=["Sessions"],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        404: {"description": "Not found"}
    }
)

@router.post("/start",response_model=SessionResponse,status_code=status.HTTP_201_CREATED)
async def start_session(
    request: SessionCreate,
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    try:

        if request.is_baseline:
            await db.execute(
                 update(WalkingSessions)
                 .where(WalkingSessions.user_id == current_user.id, WalkingSessions.is_baseline == True)
                 .values(is_baseline=False)
                )
    
        new_session = WalkingSessions(
            user_id=current_user.id,
            start_time=datetime.now(timezone.utc),
            is_baseline=request.is_baseline,
            is_processed=False,
            status=SessionStatus.RECORDING,
            notes=request.notes
        )
        
        db.add(new_session)
        await db.commit()
        await db.refresh(new_session)

        return new_session
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании сессии: {str(e)}"
        )


@router.post("/{session_id}/stop",response_model=SessionStopResponse)
async def stop_session(
    session_id: int,
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(WalkingSessions).where(WalkingSessions.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    if session.end_time is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already stopped"
        )
    try:
        session.end_time = datetime.now(timezone.utc)
        session.duration = (session.end_time - session.start_time).total_seconds()
        
        await db.commit()
        await db.refresh(session)
        
        return SessionStopResponse(
            session_id=session.id,
            start_time=session.start_time,
            end_time=session.end_time,
            duration=session.duration,
            status="stopped"
        )
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при остановке сессии: {str(e)}"
        )


@router.get("/{session_id}",response_model=SessionResponse)
async def get_session(
    session_id: int,
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):  
    result = await db.execute(select(WalkingSessions).where(WalkingSessions.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    if session.end_time is None:
        status_str = "recording"
    elif not session.is_processed:
        status_str = "processing"
    else:
        status_str = "completed"
    
    return SessionResponse(
        session_id=session.id,
        user_id=session.user_id,
        status=status_str,
        is_baseline=session.is_baseline,
        is_processed=session.is_processed,
        notes=session.notes,
        metrics = SessionMetrics.model_validate(session) if session.is_processed else None)

def determine_status(session: WalkingSessions) -> str:
    if session.end_time is None:
        return "recording"
    return "completed" if session.is_processed else "processing"

@router.get("/", response_model=List[SessionListItem])
async def get_all_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: Users = Depends(get_current_user)
):
    result = await db.execute(
        select(WalkingSessions)
        .where(WalkingSessions.user_id == current_user.id)
        .order_by(WalkingSessions.start_time.desc())
    )
    sessions = result.scalars().all()
    
    return [
        SessionListItem(
            session_id=s.id, 
            status=determine_status(s),
            is_baseline=s.is_baseline,
            notes=s.notes
        ) for s in sessions
    ]

@router.post("/{session_id}/upload",status_code=status.HTTP_200_OK)
async def upload_session_data(
    session_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(WalkingSessions).where(WalkingSessions.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    if session.status != SessionStatus.RECORDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session is not in RECORDING status (current: {session.status.value})"
        )
    if session.end_time is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session already has end_time. Cannot upload more data."
        )
    
    try:
        bin_data = await file.read()
        if len(bin_data) < 100:
            raise HTTPException(status_code=400, detail="File too small")
        session.status = SessionStatus.PROCESSING
        await db.commit()
        
        user_res = await db.execute(
            select(Users).options(selectinload(Users.profile)).where(Users.id == current_user.id)
        )
        user_obj = user_res.scalar_one_or_none()
        height = user_obj.profile.height

        meta = SessionMetadata(
            start_time=session.start_time,
            height=height,
            user_notes=session.notes,
            is_baseline=session.is_baseline,
            user_id=session.user_id,
            session_id=session.id
        )
        session.status = SessionStatus.PROCESSING
       
        db_url = str(db.get_bind().url)
    
        background_tasks.add_task(
           process_session_data,
           session_id,
           bin_data,
           meta,
           db_url)

        await db.commit()
        await db.refresh(session)

        return {
           "status": "accepted",
           "session_id": session_id
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error on uploading data: {str(e)}"
        )

async def process_session_data(session: WalkingSessions, raw_data, metadata: SessionMetadata, db_url: str):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    
    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    orchestrator = GaitAnalysisOrchestrator(
        unpack_bin=unpack_bin,
        calculate_step_metrics=calculate_step_metrics)
    from d_processing import session_pro
    orchestrator.session = session_pro
    
    async with session_factory() as db:
        try:
            res = await db.execute(select(WalkingSessions).where(WalkingSessions.id == session_id))
            session = res.scalar_one()
            summary = await run_in_threadpool(
                orchestrator.process_session,
                raw_data=raw_data,
                metadata=metadata
            )
        
            if isinstance(summary, str): 
                print(f"Algorithm Error: {summary}")
                session.status = SessionStatus.STOPPED
                session.is_processed = False
                return

            if not summary:
                session.status = SessionStatus.STOPPED
                return

            
            session.start_time = metadata.start_time
            session.end_time = summary.get('end_time')
            session.duration = summary.get('duration')

            session.user_notes = metadata.user_notes
            session.is_baseline = metadata.is_baseline
            session.user_id = metadata.user_id
            session.is_processed = True
            session.status = SessionStatus.COMPLETED.value
            session.activity_type = summary.get('activity_type', [])

            session.step_count = int(summary.get('step_count', 0))
            session.cadence = float(summary.get('cadence', 0))
            session.avg_speed = float(summary.get('avg_speed', 0))
            session.avg_peak_angular_velocity = summary.get('avg_peak_angular_velocity')
        
            # Joint Mechanics
            session.knee_angle_mean = summary.get('knee_angle_mean')
            session.knee_angle_std = summary.get('knee_angle_std')
            session.knee_angle_max = summary.get('knee_angle_max')
            session.knee_angle_min = summary.get('knee_angle_min')
            session.knee_amplitude = summary.get('knee_amplitude')
        
            session.hip_angle_mean = summary.get('hip_angle_mean')
            session.hip_angle_std = summary.get('hip_angle_std')
            session.hip_angle_max = summary.get('hip_angle_max')
            session.hip_angle_min = summary.get('hip_angle_min')
            session.hip_amplitude = summary.get('hip_amplitude')
        
            session.avg_roll = summary.get('avg_roll')
            session.avg_pitch = summary.get('avg_pitch')
            session.avg_yaw = summary.get('avg_yaw')
        
            # Variability
            session.gvi = summary.get('gvi')
            session.step_time_variability = summary.get('step_time_cv')
            session.stance_time_variability = summary.get('stance_time_cv')
            session.swing_time_variability = summary.get('swing_time_cv')
            session.knee_angle_variability = summary.get('knee_angle_cv')
            session.stride_length_variability = summary.get('stride_length_variability')

            # Symmetry & Phases
            session.avg_stance_time = summary.get('avg_stance_time')
            session.avg_swing_time = summary.get('avg_swing_time')
            session.stance_swing_ratio = summary.get('stance_swing_ratio')
            session.double_support_time = summary.get('double_support_time')
            session.avg_impact_force = summary.get('avg_impact_force')

            await db.commit()
        
        except Exception as e:
            print(f"Wrapper Error: {str(e)}")
            import traceback 
            traceback.print_exc()
            session.status = SessionStatus.STOPPED
            session.is_processed = False
            await db.rollback()
        finally:
            await engine.dispose()