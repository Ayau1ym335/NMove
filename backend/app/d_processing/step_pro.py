import numpy as np
import json
from typing import List, Dict, Any
from scipy.interpolate import interp1d
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('GaitMetrics')

@dataclass
class StepEvent:
    hs_idx: int  
    to_idx: int 
    next_hs_idx: int 

def calculate_step_metrics(
    filtered_data: np.ndarray,
    orientations: np.ndarray,
    steps: List[Any], 
    fs: int = 125
) -> List[Dict[str, Any]]:
    metrics_list = []
    n_samples = len(filtered_data)
    if isinstance(orientations, dict):
        orientation_fields = ['thigh_pitch', 'shank_pitch', 'knee_angle']
        if all(key in orientations for key in orientation_fields):
            n_orient = len(orientations['knee_angle'])
        else:
            logger.error("Orientations должен содержать поля: thigh_pitch, shank_pitch, knee_angle")
            return []
    else:
        n_orient = len(orientations)
    
    if n_orient != n_samples:
        logger.warning(f"Несоответствие размеров: filtered_data={n_samples}, orientations={n_orient}")
    
    for step_idx, step in enumerate(steps):
        try:
            if hasattr(step, 'hs_idx'):
                hs_idx = step.hs_idx
                to_idx = step.to_idx
                next_hs_idx = step.next_hs_idx
            else:
                hs_idx = step.get('hs_idx') or step.get('hs')
                to_idx = step.get('to_idx') or step.get('to')
                next_hs_idx = step.get('next_hs_idx') or step.get('next_hs')
            
            if not _validate_indices(hs_idx, to_idx, next_hs_idx, n_samples):
                logger.warning(f"Пропуск шага {step_idx}: невалидные индексы")
                continue
            
            step_metrics = _calculate_single_step_metrics(
                filtered_data=filtered_data,
                orientations=orientations,
                hs_idx=hs_idx,
                to_idx=to_idx,
                next_hs_idx=next_hs_idx,
                fs=fs,
                step_number=step_idx + 1
            )
            
            metrics_list.append(step_metrics)
            
        except Exception as e:
            logger.error(f"Ошибка при обработке шага {step_idx}: {e}")
            continue
    
    logger.info(f"Успешно обработано {len(metrics_list)} из {len(steps)} шагов")
    return metrics_list


def _validate_indices(
    hs_idx: int,
    to_idx: int,
    next_hs_idx: int,
    n_samples: int
) -> bool:
    if hs_idx is None or to_idx is None or next_hs_idx is None:
        return False

    try:
        hs_idx = int(hs_idx)
        to_idx = int(to_idx)
        next_hs_idx = int(next_hs_idx)
    except (ValueError, TypeError):
        return False
    
    if hs_idx < 0 or next_hs_idx >= n_samples:
        return False
  
    if not (hs_idx < to_idx < next_hs_idx):
        return False
   
    if (next_hs_idx - hs_idx) < 10: 
        return False
    
    return True


def _calculate_single_step_metrics(
    filtered_data: np.ndarray,
    orientations: Any,
    hs_idx: int,
    to_idx: int,
    next_hs_idx: int,
    fs: int,
    step_number: int
) -> Dict[str, Any]:
  
    step_time = (next_hs_idx - hs_idx) / fs
    stance_time = (to_idx - hs_idx) / fs
    swing_time = (next_hs_idx - to_idx) / fs
    
    stance_percent = (stance_time / step_time) * 100 if step_time > 0 else 0
    swing_percent = (swing_time / step_time) * 100 if step_time > 0 else 0
    
    cadence = 60.0 / step_time if step_time > 0 else 0
    
    if isinstance(orientations, dict):
        knee_angle_full = orientations['knee_angle']
        thigh_pitch_full = orientations.get('thigh_pitch', np.zeros_like(knee_angle_full))
        shank_pitch_full = orientations.get('shank_pitch', np.zeros_like(knee_angle_full))

        thigh_roll_full = orientations.get('thigh_roll', np.zeros_like(knee_angle_full))
        thigh_yaw_full = orientations.get('thigh_yaw', np.zeros_like(knee_angle_full))
        shank_roll_full = orientations.get('shank_roll', np.zeros_like(knee_angle_full))
        shank_yaw_full = orientations.get('shank_yaw', np.zeros_like(knee_angle_full))
    else:
        knee_angle_full = orientations['knee_angle']
        thigh_pitch_full = orientations['thigh_pitch']
        shank_pitch_full = orientations['shank_pitch']

        thigh_roll_full = orientations['thigh_roll'] if 'thigh_roll' in orientations.dtype.names else np.zeros_like(knee_angle_full)
        thigh_yaw_full = orientations['thigh_yaw'] if 'thigh_yaw' in orientations.dtype.names else np.zeros_like(knee_angle_full)
        shank_roll_full = orientations['shank_roll'] if 'shank_roll' in orientations.dtype.names else np.zeros_like(knee_angle_full)
        shank_yaw_full = orientations['shank_yaw'] if 'shank_yaw' in orientations.dtype.names else np.zeros_like(knee_angle_full)
    
    knee_angle_step = knee_angle_full[hs_idx:next_hs_idx]
    
    stance_indices = slice(hs_idx, to_idx)
    swing_indices = slice(to_idx, next_hs_idx)
    
    knee_angle_stance = knee_angle_full[stance_indices]
    knee_angle_swing = knee_angle_full[swing_indices]

    if len(knee_angle_swing) > 0:
        knee_flexion_max = float(np.max(knee_angle_swing))
    else:
        knee_flexion_max = float(np.max(knee_angle_step)) if len(knee_angle_step) > 0 else 0.0
    

    if len(knee_angle_stance) > 0:
        knee_extension_min = float(np.min(knee_angle_stance))
    else:
        knee_extension_min = float(np.min(knee_angle_step)) if len(knee_angle_step) > 0 else 0.0
    
    knee_rom = knee_flexion_max - knee_extension_min
    
    shank_pitch_stance = shank_pitch_full[stance_indices]
    shank_roll_stance = shank_roll_full[stance_indices]
    shank_yaw_stance = shank_yaw_full[stance_indices]
    
    if len(shank_pitch_stance) > 0:
        pitch_mean = float(np.mean(shank_pitch_stance))
        roll_mean = float(np.mean(shank_roll_stance))
        yaw_mean = float(np.mean(shank_yaw_stance))
    else:
        pitch_mean = 0.0
        roll_mean = 0.0
        yaw_mean = 0.0
    
    knee_curve_normalized = _normalize_to_100_points(knee_angle_step)
    knee_curve_json = json.dumps(knee_curve_normalized)
  
    gyro_shank_sagittal = filtered_data['gyro2'][hs_idx:next_hs_idx, 1] 
    peak_angular_velocity = float(np.max(np.abs(gyro_shank_sagittal))) if len(gyro_shank_sagittal) > 0 else 0.0
    
    acc_vertical = filtered_data['acc2'][hs_idx:min(hs_idx+10, next_hs_idx), 2] 
    impact_force = float(np.max(np.abs(acc_vertical))) if len(acc_vertical) > 0 else 0.0
    
    metrics = {
        'step_number': step_number,
        'hs_idx': int(hs_idx),
        'to_idx': int(to_idx),
        'next_hs_idx': int(next_hs_idx),
        'step_time': round(step_time, 4),
        'stance_time': round(stance_time, 4),
        'swing_time': round(swing_time, 4),
        'stance_percent': round(stance_percent, 2),
        'swing_percent': round(swing_percent, 2),
        'cadence': round(cadence, 2),
        'knee_flexion_max': round(knee_flexion_max, 2),
        'knee_extension_min': round(knee_extension_min, 2),
        'knee_rom': round(knee_rom, 2),
        'pitch': round(pitch_mean, 2),
        'roll': round(roll_mean, 2),
        'yaw': round(yaw_mean, 2),
        'knee_curve_json': knee_curve_json,
        'peak_angular_velocity': round(peak_angular_velocity, 2),
        'impact_force': round(impact_force, 2),
    }
    
    return metrics


def _normalize_to_100_points(signal: np.ndarray) -> List[float]:
    if len(signal) == 0:
        return [0.0] * 100
    
    if len(signal) == 1:
        return [float(signal[0])] * 100
    original_time = np.linspace(0, 100, len(signal))
    target_time = np.linspace(0, 100, 100)
    
    try:
        interpolator = interp1d(
            original_time,
            signal,
            kind='linear',
            bounds_error=False,
            fill_value='extrapolate'
        )
        
        normalized = interpolator(target_time)
        return [round(float(x), 3) for x in normalized]
        
    except Exception as e:
        logger.warning(f"Ошибка интерполяции: {e}, возвращаем нули")
        return [0.0] * 100
    


def create_database_insert_query(metrics_list: List[Dict]) -> str:
    if not metrics_list:
        return ""
    
    fields = list(metrics_list[0].keys())
    query = "INSERT INTO gait_steps (\n"
    query += "  " + ", ".join(fields) + "\n"
    query += ") VALUES\n"
    
    values_list = []
    for metrics in metrics_list:
        values = []
        for field in fields:
            value = metrics[field]
            if isinstance(value, str):
                value = value.replace("'", "''")
                values.append(f"'{value}'")
            elif value is None:
                values.append("NULL")
            else:
                values.append(str(value))
        values_list.append("  (" + ", ".join(values) + ")")
    
    query += ",\n".join(values_list) + ";"
    
    return query
