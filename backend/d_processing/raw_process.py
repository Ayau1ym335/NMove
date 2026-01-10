import numpy as np
from lowp_f import FILTER_CONFIGS, AdaptiveLowPassFilter, SegmentedAdaptiveFilter, prefiltration
from typing import Dict
from madgwick import MadgwickAHRS
import struct

def unpack_bin(file_path):
    fmt = "<fQhhhhhh" 
    struct_size = struct.calcsize(fmt)
    data = []

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(struct_size)
            if not chunk or len(chunk) < struct_size:
                break
            data.append(struct.unpack(fmt, chunk))
    
    return np.array(data, dtype=np.float64)

class AdaptiveIMUProcessor:
    def __init__(self, fs: float = 125.0, beta: float = 0.1):
        self.fs = fs
        self.beta = beta
        self.lowpass_filter = AdaptiveLowPassFilter(fs=fs)
        self.madgwick = MadgwickAHRS(sampleperiod=1/fs, beta=beta)

    def process_imu_data(
        self,
        acc_data: np.ndarray,
        gyro_data: np.ndarray
    ) -> Dict:
        acc_pre = prefiltration(acc_data, cutoff=25.0, fs=self.fs)
        gyro_pre = prefiltration(gyro_data, cutoff=25.0, fs=self.fs)

        acc_filtered = self.lowpass_filter.filter_adaptive(acc_pre)
        gyro_filtered = self.lowpass_filter.filter_adaptive(gyro_pre)

        if np.max(np.abs(gyro_filtered)) > 10: 
            gyro_rad = np.deg2rad(gyro_filtered)
        else:
            gyro_rad = gyro_filtered

        quaternions = []
        euler_angles = []

        if self.madgwick is not None:
            for i in range(len(acc_filtered)):
                self.madgwick.update_imu(gyro_rad[i], acc_filtered[i])

                q = self.madgwick.quaternion
                quaternions.append(q.copy())

                euler = self._quaternion_to_euler(q)
                euler_angles.append(euler)

        results = {
            'acc_filtered': acc_filtered,
            'gyro_filtered': gyro_filtered,
            'quaternions': np.array(quaternions) if quaternions else None,
            'euler_angles': np.array(euler_angles) if euler_angles else None,
        }

        return results

    def _quaternion_to_euler(self, q: np.ndarray) -> np.ndarray:
        w, x, y, z = q

        sinr_cosp = 2 * (w * x + y * z)
        cosr_cosp = 1 - 2 * (x * x + y * y)
        roll = np.arctan2(sinr_cosp, cosr_cosp)

        sinp = 2 * (w * y - z * x)
        if abs(sinp) >= 1:
            pitch = np.sign(sinp) * np.pi / 2
        else:
            pitch = np.arcsin(sinp)

        siny_cosp = 2 * (w * z + x * y)
        cosy_cosp = 1 - 2 * (y * y + z * z)
        yaw = np.arctan2(siny_cosp, cosy_cosp)

        return np.array([roll, pitch, yaw])