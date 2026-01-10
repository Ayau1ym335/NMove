import numpy as np
from typing import List, Dict, Optional
from scipy.signal import find_peaks

class GaitEventDetector:
    def __init__(
        self,
        sampling_rate: float = 125.0,
        hs_threshold_factor: float = 1.5,
        hs_min_distance: float = 0.4,
        to_search_window: tuple = (0.1, 0.8)
    ):
        self.sampling_rate = sampling_rate
        self.hs_threshold_factor = hs_threshold_factor
        self.hs_min_distance = hs_min_distance
        self.to_search_window = to_search_window
        
        self._hs_min_distance_samples = int(hs_min_distance * sampling_rate)
    
    def detect(self, imu_data: np.ndarray) -> List[Dict[str, int]]:
        """
        Returns:
            List of dictionaries, each containing:
            {'hs': int, 'to': int, 'next_hs': int}
        """
        if imu_data.ndim != 2 or imu_data.shape[1] != 8:
            raise ValueError(f"Expected shape (N, 8), got {imu_data.shape}")
        
        if len(imu_data) < self._hs_min_distance_samples * 2:
            return []
 
        acc_z = imu_data[:, 4]  
        gyro_y = imu_data[:, 6] 
        hs_indices = self._detect_heel_strikes(acc_z)
        if len(hs_indices) < 2:
            return []
        gait_events = self._detect_toe_offs(hs_indices, gyro_y)
        
        return gait_events
    
    def _detect_heel_strikes(self, acc_z: np.ndarray) -> np.ndarray:
        mean_acc = np.mean(acc_z)
        std_acc = np.std(acc_z)
        threshold = mean_acc + self.hs_threshold_factor * std_acc
        peaks, _ = find_peaks(
            acc_z,
            height=threshold,
            distance=self._hs_min_distance_samples
        )
        
        return peaks
    
    def _detect_toe_offs(
        self,
        hs_indices: np.ndarray,
        gyro_y: np.ndarray
    ) -> List[Dict[str, int]]:
        gait_events = []
        
        for i in range(len(hs_indices) - 1):
            hs_current = int(hs_indices[i])
            hs_next = int(hs_indices[i + 1])
            
            stride_length = hs_next - hs_current
            search_start = hs_current + int(self.to_search_window[0] * stride_length)
            search_end = hs_current + int(self.to_search_window[1] * stride_length)
            
            search_start = max(search_start, hs_current + 1)
            search_end = min(search_end, hs_next - 1)
            
            if search_start >= search_end:
                continue
            
            to_index = self._find_toe_off_in_window(
                gyro_y,
                search_start,
                search_end
            )
            
            if to_index is not None:
                gait_events.append({
                    'hs': hs_current,
                    'to': to_index,
                    'next_hs': hs_next
                })
        
        return gait_events
    
    def _find_toe_off_in_window(
        self,
        gyro_y: np.ndarray,
        start: int,
        end: int
    ) -> Optional[int]:
        window = gyro_y[start:end]
        
        if len(window) < 3:
            return None
        
        minima, properties = find_peaks(-window, distance=5)
        
        if len(minima) == 0:
            to_relative = np.argmin(window)
            return start + to_relative
        
        prominences = properties.get('prominences', np.ones(len(minima)))
        most_significant = minima[np.argmax(prominences)]
        
        return start + most_significant
        