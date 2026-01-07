# routers/sessions_r.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from typing import List, Optional
from datetime import datetime, timezone
from data.tables import get_db, WalkingSessions, Users, ActivityType, SessionStatus, RawData, Devices
from auth import get_current_user
from schemas import (
    SessionCreate,
    SessionStopResponse,
    SessionMetrics,
    SessionListItem,
    SessionResponse,
    RawDataUpload
)

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
        new_session = WalkingSessions(
            user_id=current_user.id,
            start_time=datetime.now(timezone.utc),
            is_baseline=request.is_baseline,
            is_processed=False,
            notes=request.notes,
            activity_type=ActivityType.NONE,  # Default
            auto_detected=False  
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
        start_time=session.start_time,
        end_time=session.end_time,
        duration=session.duration,
        status=status_str,
        activity_type=session.activity_type,
        is_baseline=session.is_baseline,
        is_processed=session.is_processed,
        notes=session.notes,
        metrics = SessionMetrics.model_validate(session) if session.is_processed else None)

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
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
    try:
        await db.delete(session)
        await db.commit()
        return None
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail=f"Ошибка при удалении: {str(e)}")

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
            start_time=s.start_time,
            end_time=s.end_time,
            duration=s.duration or 0.0,
            status=determine_status(s),
            is_baseline=s.is_baseline,
            activity_type=s.activity_type
        ) for s in sessions
    ]

@router.post("/{session_id}/upload",status_code=status.HTTP_200_OK)
async def upload_session_data(
    session_id: int,
    data: RawDataUpload,
    background_tasks: BackgroundTasks,
    current_user: Users = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if data.session_id != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session ID mismatch: URL={session_id}, body={data.session_id}"
        )
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
        raw_data_records = []
        
        for sample in data.samples:
            raw_data_records.append({
                "session_id": session_id,
                "placement": sample.device_pos,  # 0=thigh, 1=shin
                "timestamp": sample.timestamp,
                "a_x": sample.a_x,
                "a_y": sample.a_y,
                "a_z": sample.a_z,
                "g_x": sample.g_x,
                "g_y": sample.g_y,
                "g_z": sample.g_z
            })
        
        if raw_data_records:
            await db.execute(insert(RawData),raw_data_records)
        
        session.end_time = datetime.now(timezone.utc)
        session.duration = (session.end_time - session.start_time).total_seconds()
        session.status = SessionStatus.STOPPED
        await db.commit()
        await db.refresh(session)
        
        background_tasks.add_task(
            process_session_data,
            session_id=session_id,
            db_url=str(db.get_bind().url)  
        )
        
        return {
            "status": "uploaded",
            "session_id": session.id,
            "samples_count": len(data.samples),
            "duration": session.duration,
            "message": "Data uploaded successfully. Processing started in background."
        }
    
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error oon uploading data: {str(e)}"
        )


async def process_session_data(session_id: int, db_url: str):
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    
    engine = create_async_engine(db_url)
    AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(WalkingSessions).where(WalkingSessions.id == session_id))
            session = result.scalar_one_or_none()
            
            if not session:
                print(f"ERROR: Session {session_id} not found")
                return
            session.status = SessionStatus.PROCESSING
            await db.commit()
            result = await db.execute(
                select(RawData)
                .where(RawData.session_id == session_id)
                .order_by(RawData.timestamp)
            )
            raw_data = result.scalars().all()
            
            if not raw_data:
                print(f"WARNING: No raw data found for session {session_id}")
                session.status = SessionStatus.STOPPED
                await db.commit()
                return
            
            # =========================================
            # ЗДЕСЬ БУДУТ АЛГОРИТМЫ АНАЛИЗА (НЕДЕЛЯ 3)
            # =========================================
            
           

            session.is_processed = True
            session.status = SessionStatus.COMPLETED
            
            await db.commit()
            
            print(f" Session {session_id} processed successfully")
            print(f"   Steps: {session.step_count}, Cadence: {session.cadence}")
        
        except Exception as e:
            print(f"❌ ERROR processing session {session_id}: {str(e)}")
            try:
                session.status = SessionStatus.STOPPED
                session.is_processed = False
                await db.commit()
            except:
                pass
        finally:
            await engine.dispose()