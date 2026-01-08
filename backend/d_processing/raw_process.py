import numpy as np
from lowp_f import FILTER_CONFIGS, AdaptiveLowPassFilter, SegmentedAdaptiveFilter
from typing import Dict
from madgwick import MadgwickAHRS


class AdaptiveIMUProcessor:
    """
    Полная обработка IMU данных:
    1. Адаптивная низкочастотная фильтрация
    2. Madgwick фильтр для ориентации
    3. Расчет углов Эйлера
    """

    def __init__(self, fs: float = 125.0, beta: float = 0.1):
        """
        Args:
            fs: Частота дискретизации
            beta: Madgwick beta gain (обычно 0.1 - 0.5)
        """
        self.fs = fs
        self.beta = beta
        self.lowpass_filter = AdaptiveLowPassFilter(fs=fs)

        if MADGWICK_AVAILABLE:
            self.madgwick = MadgwickAHRS(sampleperiod=1/fs, beta=beta)
        else:
            self.madgwick = None

    def process_imu_data(
        self,
        acc_data: np.ndarray,
        gyro_data: np.ndarray,
        mag_data: np.ndarray = None
    ) -> Dict:
        """
        Полная обработка IMU данных

        Args:
            acc_data: Ускорение [N, 3] (m/s²)
            gyro_data: Угловая скорость [N, 3] (rad/s или deg/s)
            mag_data: Магнитометр [N, 3] (опционально)

        Returns:
            results: Словарь с обработанными данными
        """
        # 1. Адаптивная фильтрация
        acc_filtered, activity, metrics = self.lowpass_filter.filter_adaptive(
            acc_data,
            return_activity=True
        )
        gyro_filtered = self.lowpass_filter.filter_adaptive(gyro_data)

        # 2. Конвертировать gyro в rad/s если нужно
        if np.max(np.abs(gyro_filtered)) > 10:  # Похоже на deg/s
            gyro_rad = np.deg2rad(gyro_filtered)
        else:
            gyro_rad = gyro_filtered

        # 3. Madgwick filter для ориентации
        quaternions = []
        euler_angles = []

        if self.madgwick is not None:
            for i in range(len(acc_filtered)):
                if mag_data is not None:
                    self.madgwick.update(
                        gyro_rad[i],
                        acc_filtered[i],
                        mag_data[i]
                    )
                else:
                    self.madgwick.update_imu(
                        gyro_rad[i],
                        acc_filtered[i]
                    )

                q = self.madgwick.quaternion
                quaternions.append(q.copy())

                # Конвертировать в Euler
                euler = self._quaternion_to_euler(q)
                euler_angles.append(euler)

        results = {
            'acc_filtered': acc_filtered,
            'gyro_filtered': gyro_filtered,
            'activity': activity,
            'activity_metrics': metrics,
            'quaternions': np.array(quaternions) if quaternions else None,
            'euler_angles': np.array(euler_angles) if euler_angles else None,
            'cutoff_used': FILTER_CONFIGS[activity].cutoff_freq
        }

        return results

    def _quaternion_to_euler(self, q: np.ndarray) -> np.ndarray:
        """
        Конвертировать quaternion в Euler angles (roll, pitch, yaw)
        """
        w, x, y, z = q

        # Roll (x-axis rotation)
        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = np.arctan2(sinr_cosp, cosr_cosp)

        # Pitch (y-axis rotation)
        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = np.sign(sinp) * np.pi / 2
        else:
            pitch = np.arcsin(sinp)

        # Yaw (z-axis rotation)
        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = np.arctan2(siny_cosp, cosy_cosp)

        return np.array([roll, pitch, yaw])