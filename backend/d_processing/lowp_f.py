import numpy as np
from scipy.signal import butter, filtfilt
from detect_act import ActivityDetector, ActivityType
from typing import Tuple
from dataclasses import dataclass

@dataclass
class FilterConfig:
    activity: ActivityType
    cutoff_freq: float  # Hz

FILTER_CONFIGS = {
    ActivityType.STANDING: FilterConfig(activity=ActivityType.STANDING,cutoff_freq=25.0),
    ActivityType.WALKING: FilterConfig(activity=ActivityType.WALKING,cutoff_freq=6.0),
    ActivityType.STAIRS: FilterConfig(activity=ActivityType.STAIRS,cutoff_freq=11.0),
    ActivityType.RUNNING: FilterConfig(activity=ActivityType.RUNNING,cutoff_freq=18.0),
    ActivityType.JUMPING: FilterConfig(activity=ActivityType.JUMPING,cutoff_freq=35.0),
    ActivityType.UNKNOWN: FilterConfig(activity=ActivityType.UNKNOWN,cutoff_freq=10.0)
}

def prefiltration(data: np.ndarray, cutoff: float = 25.0, fs: float = 125.0): 
    order = 4  
    nyq = 0.5 * fs
    normal_cutoff = cutoff / nyq
    if normal_cutoff >= 1.0:
            normal_cutoff = 0.99
    b, a = butter(order, normal_cutoff, btype='lowpass')
    if data.ndim == 2:
        filtered = np.zeros_like(data)
        for i in range(data.shape[1]):
            filtered[:, i] = filtfilt(b, a, data[:, i])
        return filtered
    else:
        return filtfilt(b, a, data)

class AdaptiveLowPassFilter:
    def __init__(self, fs: float = 125.0, order: int = 4, window_size: float = 2.0):
        self.fs = fs
        self.order = order
        self.detector = ActivityDetector(fs=fs, window_size=window_size)

    def filter_adaptive(self, data: np.ndarray):
        activity = self.detector.detect_activity(data)
        config = FILTER_CONFIGS[activity]
        cutoff_freq = config.cutoff_freq
        filtered_data = self._apply_lowpass(data, cutoff_freq)

        return filtered_data

    def _apply_lowpass(self, data: np.ndarray, cutoff_freq: float) -> np.ndarray:
        nyq = 0.5 * self.fs
        normal_cutoff = cutoff_freq / nyq
        if normal_cutoff >= 1.0:
            normal_cutoff = 0.99

        b, a = butter(self.order, normal_cutoff, btype='lowpass')
        if data.ndim == 2:
            filtered = np.zeros_like(data)
            for i in range(data.shape[1]):
                filtered[:, i] = filtfilt(b, a, data[:, i])
            return filtered
        else:
            return filtfilt(b, a, data)

class SegmentedAdaptiveFilter:
    def __init__(self, fs: float = 125.0, segment_duration: float = 2.0):
        self.fs = fs
        self.segment_duration = segment_duration
        self.segment_samples = int(segment_duration * fs)
        self.filter = AdaptiveLowPassFilter(fs=fs, window_size=segment_duration)

    def filter_segmented(
        self,
        data: np.ndarray,
        overlap: float = 0.5
    ) -> Tuple[np.ndarray, list]:
        n_samples = len(data)
        step = int(self.segment_samples * (1 - overlap))

        filtered_data = np.zeros_like(data)
        activities = []

        for start in range(0, n_samples - self.segment_samples + 1, step):
            end = start + self.segment_samples

            segment = data[start:end]
            filtered_segment, activity = self.filter.filter_adaptive(segment)
            activities.append({
                'start': start / self.fs,
                'end': end / self.fs,
                'activity': activity
            })
            if start == 0:
                filtered_data[start:end] = filtered_segment
            else:
                blend_samples = int(self.segment_samples * overlap)
                blend_weights = np.linspace(0, 1, blend_samples)

                overlap_start = start
                overlap_end = start + blend_samples

                filtered_data[overlap_start:overlap_end] = (
                    filtered_data[overlap_start:overlap_end] * (1 - blend_weights) +
                    filtered_segment[:blend_samples] * blend_weights
                )

                filtered_data[overlap_end:end] = filtered_segment[blend_samples:]

        return filtered_data, activities




