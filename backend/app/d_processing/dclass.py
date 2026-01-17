from dataclasses import dataclass, field
import datetime
import numpy as np
from typing import Optional, Dict
from app.data.tables import ActivityType

@dataclass
class Metadata:
    start_time: datetime
    height: float
    user_notes: Optional[str] = None
    is_baseline: bool = False
    user_id: Optional[int] = None
    device_id: Optional[int] = None
    session_id: Optional[int] = None

@dataclass
class SensorCalibration:
    acc_bias: np.ndarray 
    acc_scale: np.ndarray  
    gyro_bias: np.ndarray 
    gyro_scale: np.ndarray = None
    rotation_matrix: Optional[np.ndarray] = None 
    
    def to_dict(self) -> dict:
        return {
            'acc_bias': self.acc_bias.tolist(),
            'acc_scale': self.acc_scale.tolist(),
            'gyro_bias': self.gyro_bias.tolist(),
            'rotation_matrix': self.rotation_matrix.tolist() if self.rotation_matrix is not None else None
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'SensorCalibration':
        rotation = np.array(data['rotation_matrix']) if data.get('rotation_matrix') is not None else None
        return cls(
            acc_bias=np.array(data['acc_bias'], dtype=np.float32),
            acc_scale=np.array(data['acc_scale'], dtype=np.float32),
            gyro_bias=np.array(data['gyro_bias'], dtype=np.float32),
            rotation_matrix=rotation
        )

@dataclass
class StepEvent:
    hs_idx: int  
    to_idx: int 
    next_hs_idx: int 

@dataclass
class GaitCycle:
    def to_dict(self) -> Dict:
        return {
            'hs': self.hs_idx,
            'to': self.to_idx,
            'next_hs': self.next_hs_idx,
            'ms': self.ms_idx,
            'duration': self.duration,
            'stride_time': self.stride_time,
            'stance_time': self.stance_time,
            'swing_time': self.swing_time,
            'cadence': self.cadence
        }

@dataclass
class DetectorConfig:
    sampling_rate: int = 125
    min_step_duration: float = 0.5  
    max_step_duration: float = 2.5 
    
    ms_peak_height_factor: float = 1.5  
    ms_peak_prominence_factor: float = 0.5 
    ms_peak_distance: Optional[int] = None 

    hs_search_window: float = 0.3
    hs_acc_threshold_factor: float = 0.3  
    
    to_search_window: float = 0.4
    to_gyro_prominence_factor: float = 0.2 
    
    enable_outlier_removal: bool = True
    outlier_std_threshold: float = 2.5  
    
    def __post_init__(self):
        if self.ms_peak_distance is None:
            self.ms_peak_distance = int(self.min_step_duration * self.sampling_rate)

@dataclass
class FilterConfig:
    cutoff_frequencies: Dict[ActivityType, float] = None
    filter_order: int = 4  
    transition_duration: float = 0.5  
    transition_type: str = "cosine"  
    sampling_rate: int = 125 
    
    def __post_init__(self):
        if self.cutoff_frequencies is None:
            self.cutoff_frequencies = {
                ActivityType.STANDING: 2.0, 
                ActivityType.WALKING: 6.0,  
                ActivityType.STAIRS: 7.0,     
                ActivityType.RUNNING: 12.0,
                ActivityType.JUMPING: 15.0,  
                ActivityType.UNKNOWN: 8.0
            }

@dataclass
class ActivityFeatures:
    sma_thigh: float 
    sma_shank: float 
    
    mag_mean_thigh: float 
    mag_mean_shank: float 
    mag_std_thigh: float
    mag_std_shank: float 
    mag_ratio: float       
    
    cadence: float  
    spectral_energy_thigh: float 
    spectral_energy_shank: float
    dominant_freq_thigh: float  
    dominant_freq_shank: float 
    
    peak_count_shank: int 
    vertical_variance: float 

@dataclass
class DetectionConfig:
    window_size: float = 2.0  
    window_overlap: float = 0.5 
    sampling_rate: int = 125
    
    standing_sma_max: float = 0.5
    standing_std_max: float = 0.3
    
    walking_sma_min: float = 0.5
    walking_sma_max: float = 3.0
    walking_cadence_min: float = 80 
    walking_cadence_max: float = 140
    walking_energy_max: float = 50.0
    
    running_sma_min: float = 3.0
    running_cadence_min: float = 140
    running_energy_min: float = 50.0
    
    jumping_peak_threshold: float = 2.5  
    jumping_peak_count_min: int = 3
    jumping_vertical_var_min: float = 5.0
    
    stairs_mag_ratio_min: float = 1.3
    stairs_cadence_min: float = 60
    stairs_cadence_max: float = 100
    stairs_sma_min: float = 1.0
    
    freq_band_low: float = 0.5  
    freq_band_high: float = 5.0 

@dataclass
class ActivitySegment:
    activity_type: ActivityType
    start_time: float 
    end_time: float  
    confidence: float  
    features: Optional[ActivityFeatures] = None