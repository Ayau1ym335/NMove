import numpy as np
from scipy.signal import butter, filtfilt
from typing import Dict, List, Optional
from dataclasses import dataclass
from scipy import signal
from enum import Enum
from .detect_act import ActivityType
from .dclass import ActivitySegment, FilterConfig

def prefiltration(data: np.ndarray, cutoff: float = 20.0, fs: float = 125.0): 
    order = 4  
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    if normal_cutoff >= 1.0:
            normal_cutoff = 0.99
    b, a = butter(order, normal_cutoff, btype='lowpass')
    return filtfilt(b, a, data, axis=0)

class Filter:
    def __init__(self, config: Optional[FilterConfig] = None):
        self.config = config if config is not None else FilterConfig()
        self._filter_cache = {}  
        
    def process(
        self, 
        data: np.ndarray, 
        segments: List[ActivitySegment]
    ) -> np.ndarray:
        if len(data) == 0:
            return data
        
        filtered_data = np.copy(data)
        timestamps = data['timestamp']
        unique_activities = set(seg.activity_type for seg in segments)
        filtered_versions = {}
        
        for activity_type in unique_activities:
            cutoff_freq = self.config.cutoff_frequencies[activity_type]
            filtered_versions[activity_type] = self._apply_butterworth_filter(
                data, cutoff_freq
            )
        alpha_masks = self._create_alpha_masks(timestamps, segments, unique_activities)
        for field in ['acc1', 'gyro1', 'acc2', 'gyro2']:
            blended = np.zeros_like(data[field])
            
            for activity_type in unique_activities:
                alpha = alpha_masks[activity_type]  
                filtered_version = filtered_versions[activity_type][field]
                
                blended += filtered_version * alpha[:, np.newaxis]
            
            filtered_data[field] = blended
        
        return filtered_data
    
    def _apply_butterworth_filter(
        self, 
        data: np.ndarray, 
        cutoff_freq: float
    ) -> np.ndarray:
        nyquist_freq = self.config.sampling_rate / 2.0
        if cutoff_freq >= nyquist_freq:
            cutoff_freq = nyquist_freq * 0.95 
        
        filter_key = (cutoff_freq, self.config.filter_order)
        if filter_key not in self._filter_cache:
            sos = signal.butter(
                self.config.filter_order,
                cutoff_freq,
                btype='low',
                fs=self.config.sampling_rate,
                output='sos' 
            )
            self._filter_cache[filter_key] = sos
        else:
            sos = self._filter_cache[filter_key]
        
        filtered = np.copy(data)
        
        for field in ['acc1', 'gyro1', 'acc2', 'gyro2']:
            filtered[field] = signal.sosfiltfilt(
                sos, 
                data[field], 
                axis=0  
            )
        
        return filtered
    
    def _create_alpha_masks(
        self,
        timestamps: np.ndarray,
        segments: List[ActivitySegment],
        unique_activities: set
    ) -> Dict[ActivityType, np.ndarray]:
        n_samples = len(timestamps)
        transition_samples = int(self.config.transition_duration * self.config.sampling_rate)
        alpha_masks = {activity: np.zeros(n_samples) for activity in unique_activities}
        for segment in segments:
            mask = (timestamps >= segment.start_time) & (timestamps <= segment.end_time)
            segment_indices = np.where(mask)[0]
            
            if len(segment_indices) == 0:
                continue
            
            alpha = np.zeros(n_samples)
            alpha[segment_indices] = 1.0
            
            start_idx = segment_indices[0]
            end_idx = segment_indices[-1]
            
            fade_in_end = min(start_idx + transition_samples, end_idx)
            fade_in_length = fade_in_end - start_idx
            if fade_in_length > 0:
                fade_in = self._generate_fade_curve(fade_in_length, fade_type='in')
                alpha[start_idx:fade_in_end] *= fade_in
            
            fade_out_start = max(end_idx - transition_samples, start_idx)
            fade_out_length = end_idx - fade_out_start
            if fade_out_length > 0:
                fade_out = self._generate_fade_curve(fade_out_length, fade_type='out')
                alpha[fade_out_start:end_idx] *= fade_out
            
            alpha_masks[segment.activity_type] += alpha
        total_alpha = sum(alpha_masks.values())
        zero_mask = total_alpha < 1e-6
        if np.any(zero_mask):
            if ActivityType.UNKNOWN in alpha_masks:
                alpha_masks[ActivityType.UNKNOWN][zero_mask] = 1.0
                total_alpha[zero_mask] = 1.0
        
        for activity_type in alpha_masks:
            alpha_masks[activity_type] = np.divide(
                alpha_masks[activity_type],
                total_alpha,
                where=total_alpha > 1e-6,
                out=np.zeros_like(alpha_masks[activity_type])
            )
        
        return alpha_masks
    
    def _generate_fade_curve(
        self, 
        length: int, 
        fade_type: str = 'in'
    ) -> np.ndarray:
        if length <= 0:
            return np.array([])
        
        t = np.linspace(0, 1, length)
        
        if self.config.transition_type == "linear":
            curve = t
        elif self.config.transition_type == "cosine":
            curve = 0.5 * (1 - np.cos(np.pi * t))
        else:
            raise ValueError(f"Unknown transition type: {self.config.transition_type}")
        
        if fade_type == 'out':
            curve = 1.0 - curve
        
        return curve
 