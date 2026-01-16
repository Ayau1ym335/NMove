import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
import logging
from data.tables import SessionStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('SessionSummary')

@dataclass
class SessionSummary:
    session_id: Optional[int] = None
    user_id: Optional[int] = None
    session_date: Optional[str] = None
    is_baseline: bool = False
    user_notes: Optional[str] = None
    status: SessionStatus = SessionStatus.COMPLETED
    is_processed: bool = True
    
    step_count: int = 0
    duration: float = 0.0  
    
    cadence: float = 0.0  
    avg_step_time: float = 0.0
    std_step_time: float = 0.0
    avg_stance_time: float = 0.0
    std_stance_time: float = 0.0
    avg_swing_time: float = 0.0
    std_swing_time: float = 0.0
    stance_swing_ratio: float = 0.0
    
    knee_angle_mean: float = 0.0
    knee_angle_std: float = 0.0
    knee_angle_max: float = 0.0
    knee_angle_min: float = 0.0
    knee_amplitude: float = 0.0  
    avg_knee_rom: float = 0.0

    hip_angle_mean: float = 0.0
    hip_angle_std: float = 0.0
    hip_angle_max: float = 0.0
    hip_angle_min: float = 0.0
    hip_amplitude: float = 0.0
    avg_hip_rom: float = 0.0
    
    cv_step_time: float = 0.0
    cv_stance_time: float = 0.0
    cv_knee_angle: float = 0.0
    cv_hip_angle: float = 0.0
    
    gvi: float = 0.0 

    avg_roll: float = 0.0
    avg_pitch: float = 0.0
    avg_yaw: float = 0.0
    
    avg_cadence_per_step: float = 0.0
    symmetry_index: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'session_date': self.session_date,
            'is_baseline': self.is_baseline,
            'user_notes': self.user_notes,
            'status': self.status.value,
            'is_processed': self.is_processed,
            'step_count': self.step_count,
            'duration': round(self.duration, 3),
            'cadence': round(self.cadence, 2),
            'avg_step_time': round(self.avg_step_time, 4),
            'std_step_time': round(self.std_step_time, 4),
            'avg_stance_time': round(self.avg_stance_time, 4),
            'std_stance_time': round(self.std_stance_time, 4),
            'avg_swing_time': round(self.avg_swing_time, 4),
            'std_swing_time': round(self.std_swing_time, 4),
            'stance_swing_ratio': round(self.stance_swing_ratio, 3),
            'knee_angle_mean': round(self.knee_angle_mean, 2),
            'knee_angle_std': round(self.knee_angle_std, 2),
            'knee_angle_max': round(self.knee_angle_max, 2),
            'knee_angle_min': round(self.knee_angle_min, 2),
            'knee_amplitude': round(self.knee_amplitude, 2),
            'avg_knee_rom': round(self.avg_knee_rom, 2),
            'hip_angle_mean': round(self.hip_angle_mean, 2),
            'hip_angle_std': round(self.hip_angle_std, 2),
            'hip_angle_max': round(self.hip_angle_max, 2),
            'hip_angle_min': round(self.hip_angle_min, 2),
            'hip_amplitude': round(self.hip_amplitude, 2),
            'avg_hip_rom': round(self.avg_hip_rom, 2),
            'cv_step_time': round(self.cv_step_time, 2),
            'cv_stance_time': round(self.cv_stance_time, 2),
            'cv_knee_angle': round(self.cv_knee_angle, 2),
            'cv_hip_angle': round(self.cv_hip_angle, 2),
            'gvi': round(self.gvi, 2),
            'avg_roll': round(self.avg_roll, 2),
            'avg_pitch': round(self.avg_pitch, 2),
            'avg_yaw': round(self.avg_yaw, 2),
            'avg_cadence_per_step': round(self.avg_cadence_per_step, 2),
            'symmetry_index': round(self.symmetry_index, 2) if self.symmetry_index else None
        }


def calculate_session_summary(
    metrics_list: List[Dict[str, Any]],
    raw_orientation: Optional[Any] = None,
    session_metadata: Optional[Dict[str, Any]] = None
) -> SessionSummary:
    """
    raw_orientation : np.ndarray or dict, optional
        Полный массив углов Эйлера для всей сессии.
        Ожидаемые поля: roll, pitch, yaw или
        shank_roll, shank_pitch, shank_yaw
    session_metadata : Dict, optional
        Метаданные сессии: session_id, user_id, session_date,
        is_baseline, user_notes
    """
    summary = SessionSummary()

    if session_metadata:
        summary.session_id = session_metadata.get('session_id')
        summary.user_id = session_metadata.get('user_id')
        summary.session_date = session_metadata.get('session_date') or \
                               datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        summary.is_baseline = session_metadata.get('is_baseline', False)
        summary.user_notes = session_metadata.get('user_notes')
    else:
        summary.session_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if not metrics_list or len(metrics_list) == 0:
        logger.warning("Пустой список метрик, возвращаем нулевую сводку")
        summary.status = SessionStatus.FAILED
        summary.is_processed = True
        return summary
    
    try:
        summary.step_count = len(metrics_list)
        logger.info(f"Обработка {summary.step_count} шагов")
        
        step_times = _extract_field(metrics_list, 'step_time')
        stance_times = _extract_field(metrics_list, 'stance_time')
        swing_times = _extract_field(metrics_list, 'swing_time')
        cadences = _extract_field(metrics_list, 'cadence')
        
        knee_roms = _extract_field(metrics_list, 'knee_rom')
        knee_flexion_maxs = _extract_field(metrics_list, 'knee_flexion_max')
        knee_extension_mins = _extract_field(metrics_list, 'knee_extension_min')
        
        hip_angles = _extract_field(metrics_list, 'hip_angle', default=None)
        hip_roms = _extract_field(metrics_list, 'hip_rom', default=None)
    
        hs_indices = _extract_field(metrics_list, 'hs_idx')
        next_hs_indices = _extract_field(metrics_list, 'next_hs_idx')
        
        if len(hs_indices) > 0 and len(next_hs_indices) > 0:
            first_hs = hs_indices[0]
            last_hs = next_hs_indices[-1]
            summary.duration = float((last_hs - first_hs) / 125.0)
        else:
            summary.duration = float(np.sum(step_times))
       
        if summary.duration > 0:
            summary.cadence = float((summary.step_count / summary.duration) * 60.0)
    
        summary.avg_step_time = float(np.mean(step_times))
        summary.std_step_time = float(np.std(step_times))
        summary.avg_stance_time = float(np.mean(stance_times))
        summary.std_stance_time = float(np.std(stance_times))
        summary.avg_swing_time = float(np.mean(swing_times))
        summary.std_swing_time = float(np.std(swing_times))
     
        if summary.avg_swing_time > 0:
            summary.stance_swing_ratio = float(summary.avg_stance_time / summary.avg_swing_time)
        
        if len(cadences) > 0:
            summary.avg_cadence_per_step = float(np.mean(cadences))
     
        if len(knee_roms) > 0:
            summary.avg_knee_rom = float(np.mean(knee_roms))
        
            all_knee_angles = []
            for metric in metrics_list: 
                knee_curve = metric.get('knee_curve_json')
                if knee_curve:
                    import json
                    if isinstance(knee_curve, str):
                        knee_curve = json.loads(knee_curve)
                    all_knee_angles.extend(knee_curve)
            
            if all_knee_angles:
                all_knee_angles = np.array(all_knee_angles)
                summary.knee_angle_mean = float(np.mean(all_knee_angles))
                summary.knee_angle_std = float(np.std(all_knee_angles))
                summary.knee_angle_max = float(np.max(all_knee_angles))
                summary.knee_angle_min = float(np.min(all_knee_angles))
            else:
                summary.knee_angle_max = float(np.max(knee_flexion_maxs))
                summary.knee_angle_min = float(np.min(knee_extension_mins))
                summary.knee_angle_mean = float(np.mean(knee_roms))
                summary.knee_angle_std = float(np.std(knee_roms))
            
            summary.knee_amplitude = summary.knee_angle_max - summary.knee_angle_min
     
        if hip_angles is not None and len(hip_angles) > 0:
            summary.hip_angle_mean = float(np.mean(hip_angles))
            summary.hip_angle_std = float(np.std(hip_angles))
            summary.hip_angle_max = float(np.max(hip_angles))
            summary.hip_angle_min = float(np.min(hip_angles))
            summary.hip_amplitude = summary.hip_angle_max - summary.hip_angle_min
            
        if hip_roms is not None and len(hip_roms) > 0:
            summary.avg_hip_rom = float(np.mean(hip_roms))
        
        summary.cv_step_time = _calculate_cv(step_times)
        summary.cv_stance_time = _calculate_cv(stance_times)
        summary.cv_knee_angle = _calculate_cv(knee_roms)
        
        if hip_angles is not None and len(hip_angles) > 0:
            summary.cv_hip_angle = _calculate_cv(hip_angles)
        
        cv_values = [
            summary.cv_step_time,
            summary.cv_stance_time,
            _calculate_cv(swing_times)
        ]
        cv_values = [cv for cv in cv_values if cv > 0]  
        
        if cv_values:
            summary.gvi = float(np.mean(cv_values))
        
        logger.info(f"GVI (Gait Variability Index): {summary.gvi:.2f}%")
        
        if raw_orientation is not None:
            summary.avg_roll, summary.avg_pitch, summary.avg_yaw = \
                _calculate_global_orientation(raw_orientation)
            logger.info(f"Глобальная ориентация: Roll={summary.avg_roll:.2f}°, "
                       f"Pitch={summary.avg_pitch:.2f}°, Yaw={summary.avg_yaw:.2f}°")
     
        summary.status = SessionStatus.COMPLETED
        summary.is_processed = True
        
        return summary
        
    except Exception as e:
        logger.error(f"Ошибка при расчете сводки: {e}")
        summary.status = SessionStatus.STOPPED
        summary.is_processed = True
        return summary


def _extract_field(
    metrics_list: List[Dict[str, Any]],
    field_name: str,
    default: Any = 0.0
) -> np.ndarray:
    values = []
    for metric in metrics_list:
        value = metric.get(field_name, default)
        if value is not None:
            values.append(value)
    
    if not values:
        if default is None:
            return None
        return np.array([])
    
    return np.array(values, dtype=np.float64)


def _calculate_cv(data: np.ndarray) -> float:
    if len(data) == 0:
        return 0.0
    
    mean_val = np.mean(data)
    
    if mean_val == 0 or np.isnan(mean_val):
        return 0.0
    
    std_val = np.std(data)
    cv = (std_val / mean_val) * 100.0
    
    return float(cv)


def _calculate_global_orientation(
    raw_orientation: Any
) -> tuple[float, float, float]:
    try:
        if isinstance(raw_orientation, dict):
            roll = raw_orientation.get('roll') or raw_orientation.get('shank_roll')
            pitch = raw_orientation.get('pitch') or raw_orientation.get('shank_pitch')
            yaw = raw_orientation.get('yaw') or raw_orientation.get('shank_yaw')
            
            if roll is None or pitch is None or yaw is None:
                logger.warning("Не найдены поля roll/pitch/yaw в orientation")
                return 0.0, 0.0, 0.0
            
            avg_roll = float(np.mean(roll))
            avg_pitch = float(np.mean(pitch))
            avg_yaw = float(np.mean(yaw))
        elif hasattr(raw_orientation, 'dtype'):
            field_names = raw_orientation.dtype.names

            roll_field = 'roll' if 'roll' in field_names else 'shank_roll'
            pitch_field = 'pitch' if 'pitch' in field_names else 'shank_pitch'
            yaw_field = 'yaw' if 'yaw' in field_names else 'shank_yaw'
            
            if roll_field not in field_names:
                logger.warning("Не найдены поля ориентации")
                return 0.0, 0.0, 0.0
            
            avg_roll = float(np.mean(raw_orientation[roll_field]))
            avg_pitch = float(np.mean(raw_orientation[pitch_field]))
            avg_yaw = float(np.mean(raw_orientation[yaw_field]))
            
        else:
            logger.warning("Неизвестный формат raw_orientation")
            return 0.0, 0.0, 0.0
        
        return avg_roll, avg_pitch, avg_yaw
        
    except Exception as e:
        logger.error(f"Ошибка расчета глобальной ориентации: {e}")
        return 0.0, 0.0, 0.0


def create_database_insert_statement(summary: SessionSummary) -> str:
    data = summary.to_dict()
    
    fields = list(data.keys())
    values = []
    
    for field in fields:
        value = data[field]
        if value is None:
            values.append("NULL")
        elif isinstance(value, str):
            value = value.replace("'", "''")
            values.append(f"'{value}'")
        elif isinstance(value, bool):
            values.append("TRUE" if value else "FALSE")
        else:
            values.append(str(value))
    
    query = f"""INSERT INTO session_summary (
    {', '.join(fields)}
) VALUES (
    {', '.join(values)}
);"""
    
    return query
