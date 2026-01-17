import numpy as np
from dataclasses import dataclass, asdict, is_dataclass
from enum import Enum
from typing import List, Tuple, Dict, Optional, Any
from scipy import signal
from datetime import datetime

class ActivityType(Enum):
    STANDING = "standing"
    WALKING = "walking"
    RUNNING = "running"
    JUMPING = "jumping"
    STAIRS = "stairs"
    UNKNOWN = "unknown"


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
class ActivitySegment:
    activity_type: ActivityType
    start_time: float 
    end_time: float  
    confidence: float  
    features: Optional[ActivityFeatures] = None


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


class ActivityDetector:
    def __init__(self, config: Optional[DetectionConfig] = None):
        self.config = config if config is not None else DetectionConfig()
        
    def detect(self, data: np.ndarray) -> List[ActivitySegment]:
        window_samples = int(self.config.window_size * self.config.sampling_rate)
        step_samples = int((self.config.window_size - self.config.window_overlap) * 
                          self.config.sampling_rate)
        
        segments = []
        n_samples = len(data)
        
        for start_idx in range(0, n_samples - window_samples + 1, step_samples):
            end_idx = start_idx + window_samples
            window_data = data[start_idx:end_idx]
            
            features = self._extract_features(window_data)
            
            activity_type, confidence = self._classify(features)
            
            segment = ActivitySegment(
                activity_type=activity_type,
                start_time=window_data['timestamp'][0],
                end_time=window_data['timestamp'][-1],
                confidence=confidence,
                features=features
            )
            segments.append(segment)
        
        merged_segments = self._merge_segments(segments)
        
        return merged_segments
    
    def _extract_features(self, window_data: np.ndarray) -> ActivityFeatures:
        acc_thigh = window_data['acc1']
        acc_shank = window_data['acc2']  
        
        mag_thigh = np.sqrt(np.sum(acc_thigh**2, axis=1))  
        mag_shank = np.sqrt(np.sum(acc_shank**2, axis=1))  
        
        sma_thigh = np.mean(np.sum(np.abs(acc_thigh), axis=1))
        sma_shank = np.mean(np.sum(np.abs(acc_shank), axis=1))
        
        mag_mean_thigh = np.mean(mag_thigh)
        mag_mean_shank = np.mean(mag_shank)
        mag_std_thigh = np.std(mag_thigh)
        mag_std_shank = np.std(mag_shank)
        
        mag_ratio = mag_mean_shank / (mag_mean_thigh + 1e-6)
        
        window = np.hanning(len(mag_shank))
        
        fft_shank = np.fft.rfft(mag_shank * window)
        freqs = np.fft.rfftfreq(len(mag_shank), 1.0 / self.config.sampling_rate)
        
        freq_mask = (freqs >= self.config.freq_band_low) & (freqs <= self.config.freq_band_high)
        power_spectrum = np.abs(fft_shank[freq_mask])**2
        freqs_filtered = freqs[freq_mask]
        
        spectral_energy_shank = np.sum(power_spectrum)
        
        if len(power_spectrum) > 0:
            dominant_idx = np.argmax(power_spectrum)
            dominant_freq_shank = freqs_filtered[dominant_idx]
        else:
            dominant_freq_shank = 0.0
        
        cadence = dominant_freq_shank * 60 * 2
        
        fft_thigh = np.fft.rfft(mag_thigh * window)
        power_spectrum_thigh = np.abs(fft_thigh[freq_mask])**2
        spectral_energy_thigh = np.sum(power_spectrum_thigh)
        
        if len(power_spectrum_thigh) > 0:
            dominant_idx_thigh = np.argmax(power_spectrum_thigh)
            dominant_freq_thigh = freqs_filtered[dominant_idx_thigh]
        else:
            dominant_freq_thigh = 0.0
        
        peaks, _ = signal.find_peaks(
            mag_shank,
            height=self.config.jumping_peak_threshold * 9.81,  
            distance=int(self.config.sampling_rate * 0.2) 
        )
        peak_count_shank = len(peaks)
        
        vertical_variance = np.var(acc_shank[:, 2])
        
        return ActivityFeatures(
            sma_thigh=float(sma_thigh),
            sma_shank=float(sma_shank),
            mag_mean_thigh=float(mag_mean_thigh),
            mag_mean_shank=float(mag_mean_shank),
            mag_std_thigh=float(mag_std_thigh),
            mag_std_shank=float(mag_std_shank),
            mag_ratio=float(mag_ratio),
            cadence=float(cadence),
            spectral_energy_thigh=float(spectral_energy_thigh),
            spectral_energy_shank=float(spectral_energy_shank),
            dominant_freq_thigh=float(dominant_freq_thigh),
            dominant_freq_shank=float(dominant_freq_shank),
            peak_count_shank=int(peak_count_shank),
            vertical_variance=float(vertical_variance)
        )
    
    def _classify(self, features: ActivityFeatures) -> Tuple[ActivityType, float]:
        cfg = self.config
        if (features.peak_count_shank >= cfg.jumping_peak_count_min and
            features.vertical_variance >= cfg.jumping_vertical_var_min and
            features.mag_std_shank > cfg.standing_std_max * 3):
            
            confidence = min(
                features.vertical_variance / (cfg.jumping_vertical_var_min * 2),
                1.0
            )
            return ActivityType.JUMPING, confidence
        
        if (features.sma_shank <= cfg.standing_sma_max and
            features.mag_std_shank <= cfg.standing_std_max):
            
            confidence = 1.0 - (features.sma_shank / cfg.standing_sma_max)
            return ActivityType.STANDING, confidence
        
        if (features.sma_shank >= cfg.running_sma_min and
            features.cadence >= cfg.running_cadence_min and
            features.spectral_energy_shank >= cfg.running_energy_min):
            
            confidence = min(
                (features.spectral_energy_shank / cfg.running_energy_min) * 0.5 +
                (features.cadence / (cfg.running_cadence_min * 1.5)) * 0.5,
                1.0
            )
            return ActivityType.RUNNING, confidence
        
        if (features.mag_ratio >= cfg.stairs_mag_ratio_min and
            cfg.stairs_cadence_min <= features.cadence <= cfg.stairs_cadence_max and
            features.sma_shank >= cfg.stairs_sma_min):
            
            confidence = min(
                (features.mag_ratio - 1.0) * 0.5 + 0.5,
                1.0
            )
            return ActivityType.STAIRS, confidence
        
        if (cfg.walking_sma_min <= features.sma_shank <= cfg.walking_sma_max and
            cfg.walking_cadence_min <= features.cadence <= cfg.walking_cadence_max and
            features.spectral_energy_shank < cfg.walking_energy_max):
            
            cadence_center = (cfg.walking_cadence_min + cfg.walking_cadence_max) / 2
            cadence_range = cfg.walking_cadence_max - cfg.walking_cadence_min
            cadence_score = 1.0 - abs(features.cadence - cadence_center) / cadence_range
            
            confidence = max(0.5, cadence_score)
            return ActivityType.WALKING, confidence
        
        return ActivityType.UNKNOWN, 0.3
    
    def _merge_segments(self, segments: List[ActivitySegment]) -> List[ActivitySegment]:
        if len(segments) == 0:
            return []
        
        merged = []
        current = segments[0]
        
        for next_segment in segments[1:]:
            if current.activity_type == next_segment.activity_type:
                current.end_time = next_segment.end_time
                current.confidence = (current.confidence + next_segment.confidence) / 2
            else:
                merged.append(current)
                current = next_segment
        merged.append(current)
        
        return merged
    
    def get_activity_summary(self, segments: List[ActivitySegment]) -> Dict[str, float]:
        summary = {activity.value: 0.0 for activity in ActivityType}
        
        for segment in segments:
            duration = segment.end_time - segment.start_time
            summary[segment.activity_type.value] += duration
        
        return summary

def jsonb(segments: List[Any]) -> List[dict]:
    json_ready_list = []
    
    for seg in segments:
        features_data = {}
        if is_dataclass(seg.features):
            features_data = asdict(seg.features)
        elif isinstance(seg.features, dict):
            features_data = seg.features
        else:
            features_data = {"raw_data": str(seg.features)}

        segment_dict = {
            "activity_type": seg.activity_type.value if isinstance(seg.activity_type, Enum) else seg.activity_type,
            "start_time": seg.start_time.isoformat() if isinstance(seg.start_time, datetime) else seg.start_time,
            "end_time": seg.end_time.isoformat() if isinstance(seg.end_time, datetime) else seg.end_time,
            "confidence": round(float(seg.confidence), 4),
            "features": features_data  
        }
        json_ready_list.append(segment_dict)
        
    return json_ready_list