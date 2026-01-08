import numpy as np
from scipy.signal import find_peaks
from enum import Enum

class ActivityType(Enum):
    STANDING = "standing"
    WALKING = "walking"
    STAIRS = "stairs"
    RUNNING = "running"
    JUMPING = "jumping"
    UNKNOWN = "unknown"

class ActivityDetector:
    def __init__(self, fs: float = 125.0, window_size: float = 2.0):
        self.fs = fs
        self.window_size = window_size
        self.window_samples = int(window_size * fs)

    def detect_activity(self, acc_data: np.ndarray):
        if acc_data.ndim == 2:
            acc_z = acc_data[:, 2]
        else:
            acc_z = acc_data
        std = self._calculate_std(acc_z)
        dominant_freq = self._calculate_dominant_frequency(acc_z)
        peak_impact = self._calculate_peak_impact(acc_z)
        signal_roughness = self._calculate_roughness(acc_z)

        activity = self._classify_activity(
            std, dominant_freq, peak_impact, signal_roughness
        )

        return activity

    @staticmethod
    def _calculate_std(signal: np.ndarray) -> float:
        return float(np.std(signal))

    def _calculate_dominant_frequency(self, signal: np.ndarray) -> float:
        signal_detrended = signal - np.mean(signal)
        peaks, _ = find_peaks(
            signal_detrended,
            height=np.std(signal_detrended) * 0.5,
            distance=int(self.fs * 0.3)
        )
        if len(peaks) < 2:
            return 0.0
        peak_intervals = np.diff(peaks) / self.fs
        avg_interval = np.median(peak_intervals)

        if avg_interval > 0:
            frequency = 1.0 / avg_interval
        else:
            frequency = 0.0
        return frequency

    @staticmethod
    def _calculate_peak_impact(signal: np.ndarray) -> float:
        signal_detrended = signal - np.mean(signal)
        max_impact = np.max(np.abs(signal_detrended))
        return max_impact

    @staticmethod
    def _calculate_roughness(signal: np.ndarray) -> float:
        raw_std = np.std(signal) + 1e-6
        second_derivative = np.diff(signal, n=2)
        absolute_roughness = np.std(second_derivative)
        roughness = absolute_roughness / raw_std

        return float(roughness)

    @staticmethod
    def _classify_activity(
        std: float,
        dominant_freq: float,
        peak_impact: float,
        signal_roughness: float
    ) -> ActivityType:
        if std < 0.15:
            return ActivityType.STANDING
        if peak_impact > 4.0:
            return ActivityType.JUMPING
        if std > 0.8 and dominant_freq > 2.5:
            return ActivityType.RUNNING
        if 0.15 <= std <= 1.0:
            if 0.5 <= dominant_freq <= 2.5:
                if signal_roughness > 5.0:
                    return ActivityType.STAIRS
                else:
                    return ActivityType.WALKING

        return ActivityType.UNKNOWN