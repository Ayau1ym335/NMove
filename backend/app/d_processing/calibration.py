from raw_process import unpack_bin
import numpy as np
import json
from dataclasses import dataclass
from typing import Optional, Tuple
import datetime
import os

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


class Calibrator:    
    def __init__(self, storage: str = 'storage/lab_calibrations'):
        self.storage = storage
        self.sensor1_cal: Optional[SensorCalibration] = None  # Бедро
        self.sensor2_cal: Optional[SensorCalibration] = None  # Голень
        self.sampling_rate = 125 

    def __post_init__(self):
        if self.gyro_scale is None:
            self.gyro_scale = np.ones(3, dtype=np.float32)
        
    def calibrate_factory_offsets(
        self, 
        data: np.ndarray,
        position_ranges: list[Tuple[int, int]]
    ) -> Tuple[SensorCalibration, SensorCalibration]:
        assert len(position_ranges) == 6, "Требуется ровно 6 статических позиций"
        g = 9.81
        
        def calibrate_sensor(acc_data: np.ndarray, gyro_data: np.ndarray) -> SensorCalibration:
            measured_acc = np.zeros((6, 3), dtype=np.float32)
            measured_gyro = np.zeros((6, 3), dtype=np.float32)
            
            for i, (start, end) in enumerate(position_ranges):
                measured_acc[i] = np.mean(acc_data[start:end], axis=0)
                measured_gyro[i] = np.mean(gyro_data[start:end], axis=0)
            gyro_bias = np.mean(measured_gyro, axis=0)
            acc_bias = np.zeros(3, dtype=np.float32)
            acc_scale = np.ones(3, dtype=np.float32)
            
            for axis in range(3):
                pos_idx = axis * 2  
                neg_idx = axis * 2 + 1  
                
                pos_measured = measured_acc[pos_idx, axis]
                neg_measured = measured_acc[neg_idx, axis]
                
                acc_scale[axis] = (pos_measured - neg_measured) / (2 * g)
                acc_bias[axis] = (pos_measured + neg_measured) / 2
            
            return SensorCalibration(
                acc_bias=acc_bias,
                acc_scale=acc_scale,
                gyro_bias=gyro_bias,
                rotation_matrix=None 
            )
     
        self.sensor1_cal = calibrate_sensor(data['acc1'], data['gyro1'])
        self.sensor2_cal = calibrate_sensor(data['acc2'], data['gyro2'])
        
        return self.sensor1_cal, self.sensor2_cal
    
    def align_to_gravity(
        self,
        data: np.ndarray,
        duration: float = 1.5
    ) -> Tuple[np.ndarray, np.ndarray]:
        assert self.sensor1_cal is not None, "Сначала выполните лабораторную калибровку"
        assert self.sensor2_cal is not None, "Сначала выполните лабораторную калибровку"
        
        n_samples = int(duration * self.sampling_rate)
        n_samples = min(n_samples, len(data))
        
        acc1_init = (data['acc1'][:n_samples] - self.sensor1_cal.acc_bias) / self.sensor1_cal.acc_scale
        acc2_init = (data['acc2'][:n_samples] - self.sensor2_cal.acc_bias) / self.sensor2_cal.acc_scale
        
        g1_measured = np.mean(acc1_init, axis=0)  #
        g2_measured = np.mean(acc2_init, axis=0)  
        
        g1_norm = g1_measured / np.linalg.norm(g1_measured)
        g2_norm = g2_measured / np.linalg.norm(g2_measured)
        
        g_target = np.array([0, 0, -1], dtype=np.float32)
        
        def compute_rotation_matrix(g_measured_norm: np.ndarray) -> np.ndarray:
            v = np.cross(g_measured_norm, g_target)
            cos_angle = np.dot(g_measured_norm, g_target)
            if cos_angle > 0.9999:
                return np.eye(3, dtype=np.float32)
            
            elif cos_angle < -0.9999:
                if abs(g_measured_norm[0]) < 0.9:
                    perp = np.array([1, 0, 0], dtype=np.float32)
                else:
                    perp = np.array([0, 1, 0], dtype=np.float32)
                v = np.cross(g_measured_norm, perp)
                v = v / np.linalg.norm(v)
                K = np.array([
                    [0, -v[2], v[1]],
                    [v[2], 0, -v[0]],
                    [-v[1], v[0], 0]
                ], dtype=np.float32)
                return np.eye(3, dtype=np.float32) + 2 * np.dot(K, K)
            else:
                v = np.cross(g_measured_norm, g_target)
                s = np.linalg.norm(v)
                c = cos_angle
                K = np.array([
                    [0, -v[2], v[1]],
                    [v[2], 0, -v[0]],
                    [-v[1], v[0], 0]
                ], dtype=np.float32) / s 
                R = np.eye(3, dtype=np.float32) + s * K + (1 - c) * np.dot(K, K)
                return R.astype(np.float32)
        
        R1 = compute_rotation_matrix(g1_norm)
        R2 = compute_rotation_matrix(g2_norm)
        self.sensor1_cal.rotation_matrix = R1
        self.sensor2_cal.rotation_matrix = R2
        
        return R1, R2
    
    def apply(self, data: np.ndarray) -> np.ndarray:
        assert self.sensor1_cal is not None, "Калибровка не выполнена"
        assert self.sensor2_cal is not None, "Калибровка не выполнена"
        
        calibrated = np.copy(data)
        
        def apply_sensor_calibration(
            acc: np.ndarray, 
            gyro: np.ndarray, 
            cal: SensorCalibration
        ) -> Tuple[np.ndarray, np.ndarray]:
            acc_corrected = (acc - cal.acc_bias) / cal.acc_scale  
            gyro_corrected = (gyro - cal.gyro_bias) / cal.gyro_scale
            
            if cal.rotation_matrix is not None:
                acc_aligned = np.einsum('ij,nj->ni', cal.rotation_matrix, acc_corrected)
                gyro_aligned = np.einsum('ij,nj->ni', cal.rotation_matrix, gyro_corrected)
                return acc_aligned.astype(np.float32), gyro_aligned.astype(np.float32)
            
            return acc_corrected, gyro_corrected
        
        calibrated['acc1'], calibrated['gyro1'] = apply_sensor_calibration(
            data['acc1'], data['gyro1'], self.sensor1_cal
        )
        calibrated['acc2'], calibrated['gyro2'] = apply_sensor_calibration(
            data['acc2'], data['gyro2'], self.sensor2_cal
        )
        
        return calibrated
    
    def save(self, device_id):
        assert self.sensor1_cal is not None, "Калибровка не выполнена"
        assert self.sensor2_cal is not None, "Калибровка не выполнена"
        
        data = {
            'id': device_id,
            "last_update": datetime.now().strftime("%Y-%m-%d"),
            'sensor1': self.sensor1_cal.to_dict(),
            'sensor2': self.sensor2_cal.to_dict()
        }
        
        file_path = os.path.join(self.storage, f"{device_id}.json")
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
    def load(self, device_id):
        file = f"{device_id}.json"
        filepath = os.path.join(self.storage, file)
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.sensor1_cal = SensorCalibration.from_dict(data['sensor1'])
        self.sensor2_cal = SensorCalibration.from_dict(data['sensor2'])
