import numpy as np
from typing import List, Dict, Optional, Any
import logging
from app.data.tables import SessionStatus
from .dclass import Metadata
from datetime import timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('SessionSummary')

def calculate_session_summary(
    metrics_list: List[Dict[str, Any]],
    orientation: np.ndarray,
    activities,
    session_metadata: Metadata
) -> Dict[str, Any]:
    if not metrics_list or len(metrics_list) == 0:
        logger.warning("Empty metrics list - no steps detected.")
        return None

    filtering_result = _filter_artifacts(metrics_list)
    clean_metrics = filtering_result['clean_data']
    
    if not clean_metrics:
        logger.warning("All steps were filtered out as artifacts!")
        return None

    basic_stats = _calculate_basic_temporal_stats(clean_metrics) 
    kinematic_stats = _calculate_kinematic_aggregation(clean_metrics)
    variability_stats = _calculate_variability_metrics(clean_metrics)
    gvi = _calculate_gvi(variability_stats)
    orientation_stats = _calculate_global_orientation(orientation)
    clinical_stats = _calculate_clinical_metrics(clean_metrics)
    avg_speed = _calculate_speed(clean_metrics, session_metadata)
   
    summary = {
        'start_time': session_metadata.start_time.isoformat(),
        'end_time': (session_metadata.start_time + timedelta(seconds=basic_stats['duration'])).isoformat(),
        'duration': basic_stats['duration'],

        'user_notes': session_metadata.user_notes,
        'is_baseline': session_metadata.is_baseline,
        'user_id': session_metadata.user_id,
        'is_processed': True,
        'status': SessionStatus.COMPLETED.value,
        'activity_type': activities,
  -
        'step_count': len(clean_metrics),
        'cadence': basic_stats['cadence'],
        'avg_speed': avg_speed['avg_speed'],
        'avg_step_time': basic_stats['avg_step_time'],
        'avg_stance_time': basic_stats['avg_stance_time'],
        'avg_swing_time': basic_stats['avg_swing_time'],
        'stance_swing_ratio': basic_stats['stance_swing_ratio'],
        
        'knee_angle_mean': kinematic_stats['knee_angle_mean'],
        'knee_angle_std': kinematic_stats['knee_angle_std'],
        'knee_angle_max': kinematic_stats['knee_angle_max'],
        'knee_angle_min': kinematic_stats['knee_angle_min'],
        'knee_amplitude': kinematic_stats['knee_amplitude'],
        
        'hip_angle_mean': kinematic_stats.get('hip_angle_mean'),
        'hip_angle_std': kinematic_stats.get('hip_angle_std'),
        'hip_angle_max': kinematic_stats.get('hip_angle_max'),
        'hip_angle_min': kinematic_stats.get('hip_angle_min'),
        'hip_amplitude': kinematic_stats.get('hip_amplitude'),
        
        'step_time_cv': variability_stats['step_time_cv'],
        'stance_time_cv': variability_stats['stance_time_cv'],
        'swing_time_cv': variability_stats['swing_time_cv'],
        'knee_angle_cv': variability_stats['knee_angle_cv'],
        
        'gvi': gvi,
        
        'avg_roll': orientation_stats['avg_roll'],
        'avg_pitch': orientation_stats['avg_pitch'],
        'avg_yaw': orientation_stats['avg_yaw'],
     
        'stride_length_variability': clinical_stats.get('stride_length_variability'),
        'double_support_time': clinical_stats.get('double_support_time'),
        'avg_impact_force': clinical_stats.get('avg_impact_force'),
        'avg_peak_angular_velocity': clinical_stats.get('avg_peak_angular_velocity'),
    }
    
    return summary


def _calculate_basic_temporal_stats(metrics_list: List[Dict]) -> Dict[str, float]:
    step_times = np.array([m['step_time'] for m in metrics_list if 'step_time' in m])
    stance_times = np.array([m['stance_time'] for m in metrics_list if 'stance_time' in m])
    swing_times = np.array([m['swing_time'] for m in metrics_list if 'swing_time' in m])
  
    step_count = len(metrics_list)
    if step_count > 0:
        first_hs = metrics_list[0].get('hs_idx', 0)
        last_hs = metrics_list[-1].get('next_hs_idx', 0)
        
        if 'step_time' in metrics_list[0]:
            duration = float(np.sum(step_times))
        else:
            duration = 0.0
    else:
        duration = 0.0

    if duration > 0:
        cadence = (step_count / duration) * 60.0
    else:
        cadence = 0.0

    avg_stance_time = float(np.mean(stance_times)) if len(stance_times) > 0 else 0.0
    avg_swing_time = float(np.mean(swing_times)) if len(swing_times) > 0 else 0.0
    
    if avg_swing_time > 0:
        stance_swing_ratio = avg_stance_time / avg_swing_time
    else:
        stance_swing_ratio = 0.0
    
    return {
        'step_count': int(step_count),
        'duration': round(duration, 3),
        'cadence': round(cadence, 2),
        'avg_stance_time': round(avg_stance_time, 4),
        'avg_swing_time': round(avg_swing_time, 4),
        'stance_swing_ratio': round(stance_swing_ratio, 3)
    }

def _calculate_kinematic_aggregation(metrics_list: List[Dict]) -> Dict[str, Optional[float]]:
    knee_flexion_max_values = np.array([
        m['knee_flexion_max'] for m in metrics_list 
        if 'knee_flexion_max' in m
    ])
    knee_extension_min_values = np.array([
        m['knee_extension_min'] for m in metrics_list 
        if 'knee_extension_min' in m
    ])
    knee_rom_values = np.array([
        m['knee_rom'] for m in metrics_list 
        if 'knee_rom' in m
    ])
    
    all_knee_angles = []
    for m in metrics_list:
        if 'knee_curve_json' in m:
            import json
            try:
                curve = json.loads(m['knee_curve_json'])
                all_knee_angles.extend(curve)
            except:
                pass
    
    all_knee_angles = np.array(all_knee_angles) if all_knee_angles else np.array([])
    
    stats = {
        'knee_angle_mean': float(np.mean(all_knee_angles)) if len(all_knee_angles) > 0 else 0.0,
        'knee_angle_std': float(np.std(all_knee_angles)) if len(all_knee_angles) > 0 else 0.0,
        'knee_angle_max': float(np.max(knee_flexion_max_values)) if len(knee_flexion_max_values) > 0 else 0.0,
        'knee_angle_min': float(np.min(knee_extension_min_values)) if len(knee_extension_min_values) > 0 else 0.0,
    }
    
    if stats['knee_angle_max'] > 0 or stats['knee_angle_min'] != 0:
        stats['knee_amplitude'] = stats['knee_angle_max'] - stats['knee_angle_min']
    else:
        stats['knee_amplitude'] = 0.0
    
    hip_flexion_values = np.array([
        m['hip_flexion_max'] for m in metrics_list 
        if 'hip_flexion_max' in m
    ])
    hip_extension_values = np.array([
        m['hip_extension_min'] for m in metrics_list 
        if 'hip_extension_min' in m
    ])
    
    if len(hip_flexion_values) > 0:
        stats['hip_angle_mean'] = float(np.mean(hip_flexion_values))
        stats['hip_angle_std'] = float(np.std(hip_flexion_values))
        stats['hip_angle_max'] = float(np.max(hip_flexion_values))
        stats['hip_angle_min'] = float(np.min(hip_extension_values)) if len(hip_extension_values) > 0 else 0.0
        stats['hip_amplitude'] = stats['hip_angle_max'] - stats['hip_angle_min']
    else:
        stats['hip_angle_mean'] = None
        stats['hip_angle_std'] = None
        stats['hip_angle_max'] = None
        stats['hip_angle_min'] = None
        stats['hip_amplitude'] = None
    
    for key in stats:
        if stats[key] is not None:
            stats[key] = round(stats[key], 2)
    
    return stats


def _calculate_variability_metrics(metrics_list: List[Dict]) -> Dict[str, float]:
    def calculate_cv(values: np.ndarray) -> float:
        if len(values) == 0 or np.mean(values) == 0:
            return 0.0
        return float((np.std(values) / np.mean(values)) * 100)
    
    step_times = np.array([m['step_time'] for m in metrics_list if 'step_time' in m])
    stance_times = np.array([m['stance_time'] for m in metrics_list if 'stance_time' in m])
    swing_times = np.array([m['swing_time'] for m in metrics_list if 'swing_time' in m])
    cadences = np.array([m.get('cadence', 0) for m in metrics_list if 'cadence' in m])
    
    knee_roms = np.array([m['knee_rom'] for m in metrics_list if 'knee_rom' in m])
    variability = {
        'step_time_cv': round(calculate_cv(step_times), 2),
        'stance_time_cv': round(calculate_cv(stance_times), 2),
        'swing_time_cv': round(calculate_cv(swing_times), 2),
        'knee_angle_cv': round(calculate_cv(knee_roms), 2),
    }
    
    return variability


def _calculate_gvi(variability_stats: Dict[str, float]) -> float:
    temporal_cvs = [
        variability_stats['step_time_cv'],
        variability_stats['stance_time_cv'],
        variability_stats['swing_time_cv'],
    ]
    
    temporal_cvs = [cv for cv in temporal_cvs if cv > 0]
    
    if len(temporal_cvs) == 0:
        return 0.0
    
    gvi = float(np.mean(temporal_cvs))
    return round(gvi, 2)


def _calculate_global_orientation(orientation: np.ndarray) -> Dict[str, float]:
    stats = {}
    def safe_mean(field_name: str) -> float:
        if isinstance(orientation, dict):
            if field_name in orientation:
                values = orientation[field_name]
                return float(np.mean(values)) if len(values) > 0 else 0.0
        else:
            if field_name in orientation.dtype.names:
                values = orientation[field_name]
                return float(np.mean(values)) if len(values) > 0 else 0.0
        return 0.0
    
    stats['avg_roll'] = round(safe_mean('shank_roll'), 2)
    stats['avg_pitch'] = round(safe_mean('shank_pitch'), 2)
    stats['avg_yaw'] = round(safe_mean('shank_yaw'), 2)
    
    return stats

def _calculate_clinical_metrics(metrics_list: List[Dict]) -> Dict[str, Optional[float]]:
    clinical = {}
    
    impact_forces = np.array([
        m.get('impact_force', 0) for m in metrics_list 
        if 'impact_force' in m
    ])
    if len(impact_forces) > 0:
        clinical['avg_impact_force'] = round(float(np.mean(impact_forces)), 2)
    else:
        clinical['avg_impact_force'] = None
    
    peak_velocities = np.array([
        m.get('peak_angular_velocity', 0) for m in metrics_list 
        if 'peak_angular_velocity' in m
    ])
    if len(peak_velocities) > 0:
        clinical['avg_peak_angular_velocity'] = round(float(np.mean(peak_velocities)), 2)
    else:
        clinical['avg_peak_angular_velocity'] = None
    
    step_times = np.array([m['step_time'] for m in metrics_list if 'step_time' in m])
    if len(step_times) > 1:
        stride_variability = float(np.std(step_times) / np.mean(step_times) * 100)
        clinical['stride_length_variability'] = round(stride_variability, 2)
    else:
        clinical['stride_length_variability'] = None
  
    stance_times = np.array([m['stance_time'] for m in metrics_list if 'stance_time' in m])
    step_times_for_double = np.array([m['step_time'] for m in metrics_list if 'step_time' in m])
    
    if len(stance_times) > 0 and len(step_times_for_double) > 0:
        avg_stance_percent = np.mean(stance_times / step_times_for_double) * 100
        if avg_stance_percent > 50:
            double_support_estimate = (avg_stance_percent - 50) * 2
            clinical['double_support_time'] = round(double_support_estimate, 2)
        else:
            clinical['double_support_time'] = 0.0
    else:
        clinical['double_support_time'] = None
    
    return clinical

def _calculate_speed(metrics_list: List[Dict], metadata: Metadata = None):
    step_count = len(metrics_list)
    step_times = np.array([m['step_time'] for m in metrics_list if 'step_time' in m])
    duration = float(np.sum(step_times)) if step_count > 0 else 0.0

    if metadata and getattr(metadata, 'height', None):
        height_m = metadata.height / 100.0 if metadata.height > 3.0 else metadata.height
        base_step_length = height_m * 0.413
        leg_length = height_m * 0.53
    else:
        base_step_length = 0.7
        leg_length = 0.9

    avg_hip_rom = np.mean([m.get('knee_rom', 30) for m in metrics_list]) / 1.5
    dynamic_step_length = 2 * leg_length * np.sin(np.radians(avg_hip_rom / 2))
    final_step_length = max(dynamic_step_length, base_step_length * 0.8)

    total_distance = step_count * final_step_length
    avg_speed = total_distance / duration if duration > 0 else 0.0

    return {'avg_speed': round(avg_speed, 2)}


def _filter_artifacts(metrics_list: List[Dict]) -> Dict:
    if not metrics_list:
        return {'clean_data': [], 'excluded_count': 0, 'stops_detected': 0}

    total_steps = len(metrics_list)
    valid_steps = metrics_list
    
    valid_steps = [
        m for m in valid_steps 
        if 0.25 <= m.get('step_time', 0) <= 2.5
    ]
    
    stops_detected = total_steps - len(valid_steps)
    if len(valid_steps) < 10:
        return {
            'clean_data': valid_steps, 
            'excluded_count': stops_detected, 
            'stops_detected': stops_detected
        }
    
    step_times = np.array([m['step_time'] for m in valid_steps])
    
    Q1 = np.percentile(step_times, 25)
    Q3 = np.percentile(step_times, 75)
    IQR = Q3 - Q1
    
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    
    clean_data = [
        m for m in valid_steps 
        if lower_bound <= m['step_time'] <= upper_bound
    ]
    
    excluded_count = total_steps - len(clean_data)
    
    return {
        'clean_data': clean_data,          
        'excluded_count': excluded_count,  
        'stops_detected': stops_detected
    }