import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum
from datetime import datetime, timezone
import json
from data.tables import SideEnum, ActivityType
import pandas as pd

@dataclass
class StepEvent:
    hs_idx: int  
    to_idx: int 
    next_hs_idx: int 
    timestamp_hs: float


@dataclass
class OrientationData:
    """Данные ориентации для всех сегментов"""
    # Бедро (Thigh)
    thigh_roll: np.ndarray
    thigh_pitch: np.ndarray
    thigh_yaw: np.ndarray
    
    # Голень (Shank)
    shank_roll: np.ndarray
    shank_pitch: np.ndarray
    shank_yaw: np.ndarray
    
    # Стопа (Foot) - если есть
    foot_roll: Optional[np.ndarray] = None
    foot_pitch: Optional[np.ndarray] = None
    foot_yaw: Optional[np.ndarray] = None
    
    # Туловище (Trunk) - если есть
    trunk_roll: Optional[np.ndarray] = None
    trunk_pitch: Optional[np.ndarray] = None
    trunk_yaw: Optional[np.ndarray] = None


@dataclass
class ActivitySegment:
    start_idx: int
    end_idx: int
    activity_type: ActivityType
    start_time: float
    end_time: float


@dataclass
class StepMetrics:
    timestamp: datetime
    step_number: int
    side: SideEnum
    roll: float
    pitch: float
    yaw: float
    knee_angle: float
    hip_angle: float
    ankle_angle: float
    stance_time: float
    swing_time: float
    step_time: float
    knee_flexion_max: float
    knee_extension_min: float
    knee_rom: float
    trunk_lean_at_hs: float
    knee_curve_json: str
    activity_type: Optional[str] = None
    cadence: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp,
            'step_number': self.step_number,
            'side': self.side.value,
            'roll': float(self.roll),
            'pitch': float(self.pitch),
            'yaw': float(self.yaw),
            'knee_angle': float(self.knee_angle),
            'hip_angle': float(self.hip_angle),
            'ankle_angle': float(self.ankle_angle),
            'stance_time': float(self.stance_time),
            'swing_time': float(self.swing_time),
            'step_time': float(self.step_time),
            'knee_flexion_max': float(self.knee_flexion_max),
            'knee_extension_min': float(self.knee_extension_min),
            'knee_rom': float(self.knee_rom),
            'trunk_lean_at_hs': float(self.trunk_lean_at_hs),
            'knee_curve_json': self.knee_curve_json,
            'activity_type': self.activity_type,
            'cadence': float(self.cadence) if self.cadence else None
        }

class StepMetricsCalculator:
    def __init__(self, sampling_rate: int = 125):
        self.sampling_rate = sampling_rate
    
    def calculate_step_metrics(
        self,
        step_events: List[StepEvent],
        orientation_data: OrientationData,
        activity_segments: List[ActivitySegment],
        session_start_time: Optional[datetime] = None,
        default_side: SideEnum = SideEnum.RIGHT
    ) -> List[StepMetrics]:
        metrics_list = []
        
        if session_start_time is None:
            session_start_time = datetime.now(timezone.utc)
        
        for step_num, step in enumerate(step_events, start=1):
            side = self._determine_step_side(step_num, default_side)
            metrics = self._calculate_single_step_metrics(
                step=step,
                step_number=step_num,
                side=side,
                orientation_data=orientation_data,
                activity_segments=activity_segments,
                session_start_time=session_start_time
            )
            
            metrics_list.append(metrics)
        
        return metrics_list
    
    def _calculate_single_step_metrics(
        self,
        step: StepEvent,
        step_number: int,
        side: SideEnum,
        orientation_data: OrientationData,
        activity_segments: List[ActivitySegment],
        session_start_time: datetime
    ) -> StepMetrics:
        hs_idx = step.hs_idx
        to_idx = step.to_idx
        next_hs_idx = step.next_hs_idx
        
        step_slice = slice(hs_idx, next_hs_idx)
        
        step_time = (next_hs_idx - hs_idx) / self.sampling_rate
        stance_time = (to_idx - hs_idx) / self.sampling_rate
        swing_time = (next_hs_idx - to_idx) / self.sampling_rate
        cadence = 60.0 / step_time 

        roll = float(np.mean(orientation_data.hank_roll[step_slice]))
        pitch = float(np.mean(orientation_data.shank_pitch[step_slice]))
        yaw = float(np.mean(orientation_data.shank_yaw[step_slice]))
        
        knee_angles = self._calculate_knee_angle(
            orientation_data.thigh_pitch[step_slice],
            orientation_data.shank_pitch[step_slice]
        )
        
        hip_angles = orientation_data.thigh_pitch[step_slice]
        
        ankle_angles = self._calculate_ankle_angle(
            orientation_data.shank_pitch[step_slice],
            orientation_data.foot_pitch[step_slice] if orientation_data.foot_pitch is not None else None
        )
        
        knee_angle_mean = float(np.mean(knee_angles))
        hip_angle_mean = float(np.mean(hip_angles))
        ankle_angle_mean = float(np.mean(ankle_angles))
        
        knee_flexion_max = float(np.max(knee_angles))
        knee_extension_min = float(np.min(knee_angles))
        knee_rom = knee_flexion_max - knee_extension_min
        
        trunk_lean_at_hs = self._calculate_trunk_lean_at_hs(
            orientation_data.trunk_pitch,
            hs_idx
        )

        knee_curve_normalized = self._normalize_curve(knee_angles, n_points=100)
        knee_curve_json = json.dumps(knee_curve_normalized.tolist())
    
        activity_type = self._get_activity_for_step(
            step.timestamp_hs,
            activity_segments
        )
    
        step_timestamp = session_start_time + \
                        pd.Timedelta(seconds=step.timestamp_hs)
    
        metrics = StepMetrics(
            timestamp=step_timestamp,
            step_number=step_number,
            side=side,
            roll=roll,
            pitch=pitch,
            yaw=yaw,
            knee_angle=knee_angle_mean,
            hip_angle=hip_angle_mean,
            ankle_angle=ankle_angle_mean,
            stance_time=stance_time,
            swing_time=swing_time,
            step_time=step_time,
            knee_flexion_max=knee_flexion_max,
            knee_extension_min=knee_extension_min,
            knee_rom=knee_rom,
            trunk_lean_at_hs=trunk_lean_at_hs,
            knee_curve_json=knee_curve_json,
            activity_type=activity_type,
            cadence=cadence
        )
        
        return metrics
    
    def _calculate_knee_angle(
        self,
        thigh_pitch: np.ndarray,
        shank_pitch: np.ndarray
    ) -> np.ndarray:
        knee_angle = thigh_pitch - shank_pitch
        return knee_angle
    
    def _calculate_ankle_angle(
        self,
        shank_pitch: np.ndarray,
        foot_pitch: Optional[np.ndarray]
    ) -> np.ndarray:
        if foot_pitch is None:
            return np.zeros_like(shank_pitch)
        ankle_angle = shank_pitch - foot_pitch
        return ankle_angle
    
    def _calculate_trunk_lean_at_hs(
        self,
        trunk_pitch: Optional[np.ndarray],
        hs_idx: int
    ) -> float:
        if trunk_pitch is None or hs_idx >= len(trunk_pitch):
            return 0.0  
        return float(trunk_pitch[hs_idx])
    
    def _normalize_curve(
        self,
        curve: np.ndarray,
        n_points: int = 100
    ) -> np.ndarray:
        original_points = len(curve)
        if original_points < 2:
            return np.zeros(n_points)
        
        x_original = np.linspace(0, 100, original_points)
        x_new = np.linspace(0, 100, n_points)
        normalized = np.interp(x_new, x_original, curve)
        return normalized
    
    def _determine_step_side(
        self,
        step_number: int,
        default_side: SideEnum
    ) -> SideEnum:
        if step_number % 2 == 1:
            return default_side
        else:
            return SideEnum.LEFT if default_side == SideEnum.RIGHT else SideEnum.RIGHT
    
    def _get_activity_for_step(
        self,
        step_timestamp: float,
        activity_segments: List[ActivitySegment]
    ) -> Optional[str]:
        for segment in activity_segments:
            if segment.start_time <= step_timestamp <= segment.end_time:
                return segment.activity_type.value
        
        return None
