import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from scipy import signal
from .dclass import GaitCycle, DetectorConfig

class StepDetector:
    def __init__(self, config: Optional[DetectorConfig] = None):
        self.config = config if config is not None else DetectorConfig()
        
    def detect_cycles(
        self,
        gyro_sagittal: np.ndarray,
        acc_vertical: np.ndarray,
        timestamps: Optional[np.ndarray] = None
    ) -> List[GaitCycle]:
        assert len(gyro_sagittal) == len(acc_vertical), \
            "Длины gyro_sagittal и acc_vertical должны совпадать"
        
        n_samples = len(gyro_sagittal)
        
        if timestamps is None:
            timestamps = np.arange(n_samples) / self.config.sampling_rate
        ms_indices = self._detect_mid_swing_peaks(gyro_sagittal)
        
        if len(ms_indices) < 2:
            return []  
        hs_indices = []
        for ms_idx in ms_indices:
            hs_idx = self._detect_heel_strike(
                gyro_sagittal, acc_vertical, ms_idx
            )
            if hs_idx is not None:
                hs_indices.append(hs_idx)
        
        if len(hs_indices) < 2:
            return []  
        cycles = []
        
        for i in range(len(hs_indices) - 1):
            current_hs = hs_indices[i]
            next_hs = hs_indices[i + 1]
            duration = (next_hs - current_hs) / self.config.sampling_rate
            if duration < self.config.min_step_duration or \
               duration > self.config.max_step_duration:
                continue
            ms_candidates = ms_indices[(ms_indices > current_hs) & (ms_indices < next_hs)]
            if len(ms_candidates) == 0:
                continue
            
            if len(ms_candidates) > 1:
                peak_heights = gyro_sagittal[ms_candidates]
                ms_idx = ms_candidates[np.argmax(peak_heights)]
            else:
                ms_idx = ms_candidates[0]
            
            to_idx = self._detect_toe_off(
                gyro_sagittal, current_hs, ms_idx
            )
            
            if to_idx is None:
                continue
            
            stride_time = duration
            stance_time = (to_idx - current_hs) / self.config.sampling_rate
            swing_time = (next_hs - to_idx) / self.config.sampling_rate
            cadence = 60.0 / stride_time  
            
            cycle = GaitCycle(
                hs_idx=current_hs,
                to_idx=to_idx,
                next_hs_idx=next_hs,
                ms_idx=ms_idx,
                duration=duration,
                stride_time=stride_time,
                stance_time=stance_time,
                swing_time=swing_time,
                cadence=cadence
            )
            cycles.append(cycle)
        
        if self.config.enable_outlier_removal and len(cycles) > 3:
            cycles = self._remove_outliers(cycles)
        
        return cycles
    
    def _detect_mid_swing_peaks(self, gyro_sagittal: np.ndarray) -> np.ndarray:
        signal_std = np.std(gyro_sagittal)
        signal_mean = np.mean(gyro_sagittal)
        
        height_threshold = signal_mean + self.config.ms_peak_height_factor * signal_std
        prominence_threshold = self.config.ms_peak_prominence_factor * signal_std
        
        peaks, properties = signal.find_peaks(
            gyro_sagittal,
            height=height_threshold,
            prominence=prominence_threshold,
            distance=self.config.ms_peak_distance
        )
        
        return peaks
    
    def _detect_heel_strike(
        self,
        gyro_sagittal: np.ndarray,
        acc_vertical: np.ndarray,
        ms_idx: int
    ) -> Optional[int]:
        search_window = int(self.config.hs_search_window * self.config.sampling_rate)
        search_start = ms_idx
        search_end = min(ms_idx + search_window, len(gyro_sagittal))
        
        if search_end <= search_start:
            return None
        
        gyro_window = gyro_sagittal[search_start:search_end]
        acc_window = acc_vertical[search_start:search_end]
        
        sign_changes = np.diff(np.sign(gyro_window))
        zero_crossings = np.where(sign_changes < 0)[0]
        
        if len(zero_crossings) > 0:
            hs_idx_relative = zero_crossings[0]
            return search_start + hs_idx_relative
        
        acc_minima, _ = signal.find_peaks(-acc_window)
        
        if len(acc_minima) > 0:
            hs_idx_relative = acc_minima[0]
            return search_start + hs_idx_relative
        
        negative_indices = np.where(gyro_window < 0)[0]
        if len(negative_indices) > 0:
            return search_start + negative_indices[0]
        
        return None
    
    def _detect_toe_off(
        self,
        gyro_sagittal: np.ndarray,
        hs_idx: int,
        ms_idx: int
    ) -> Optional[int]:
        search_window = int(self.config.to_search_window * self.config.sampling_rate)
        search_start = max(hs_idx, ms_idx - search_window)
        search_end = ms_idx
        
        if search_end <= search_start:
            return None
        
        gyro_window = gyro_sagittal[search_start:search_end]
        
        signal_std = np.std(gyro_window)
        prominence_threshold = self.config.to_gyro_prominence_factor * signal_std
        
        minima, properties = signal.find_peaks(
            -gyro_window,
            prominence=prominence_threshold
        )
        
        if len(minima) == 0:
            min_idx = np.argmin(gyro_window)
            return search_start + min_idx
        
        to_idx_relative = minima[-1]
        return search_start + to_idx_relative
    
    def _remove_outliers(self, cycles: List[GaitCycle]) -> List[GaitCycle]:
        if len(cycles) < 3:
            return cycles
        
        durations = np.array([c.duration for c in cycles])
        
        mean_duration = np.mean(durations)
        std_duration = np.std(durations)
        
        if std_duration < 1e-6:
            return cycles 
        
        z_scores = np.abs((durations - mean_duration) / std_duration)
        
        valid_mask = z_scores < self.config.outlier_std_threshold
        filtered_cycles = [c for c, valid in zip(cycles, valid_mask) if valid]
        
        return filtered_cycles
    
    def get_statistics(self, cycles: List[GaitCycle]) -> Dict[str, float]:
        if len(cycles) == 0:
            return {}
        
        stride_times = np.array([c.stride_time for c in cycles])
        stance_times = np.array([c.stance_time for c in cycles])
        swing_times = np.array([c.swing_time for c in cycles])
        cadences = np.array([c.cadence for c in cycles])
        
        stats = {
            'mean_stride_time': float(np.mean(stride_times)),
            'std_stride_time': float(np.std(stride_times)),
            'mean_stance_time': float(np.mean(stance_times)),
            'std_stance_time': float(np.std(stance_times)),
            'mean_swing_time': float(np.mean(swing_times)),
            'std_swing_time': float(np.std(swing_times)),
            
            # Cadence
            'mean_cadence': float(np.mean(cadences)),
            'std_cadence': float(np.std(cadences)),
            
            # Phase percentages
            'mean_stance_percent': float(np.mean(stance_times / stride_times * 100)),
            'mean_swing_percent': float(np.mean(swing_times / stride_times * 100)),
            
            # Variability (CV - Coefficient of Variation)
            'stride_time_cv': float(np.std(stride_times) / np.mean(stride_times) * 100),
            
            # Count
            'total_cycles': len(cycles),
            'total_duration': float(np.sum(stride_times))
        }
        
        return stats
