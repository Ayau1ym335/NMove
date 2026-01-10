import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

@dataclass
class CalibrationParams:
    acc_bias: np.ndarray  
    acc_scale: np.ndarray 
    
    gyro_bias: np.ndarray 
    gyro_scale: np.ndarray 
  
    def to_dict(self) -> Dict:
        return {
            'acc_bias': self.acc_bias.tolist(),
            'acc_scale': self.acc_scale.tolist(),
            'gyro_bias': self.gyro_bias.tolist(),
            'gyro_scale': self.gyro_scale.tolist(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(
            acc_bias=np.array(data['acc_bias']),
            acc_scale=np.array(data['acc_scale']),
            gyro_bias=np.array(data['gyro_bias']),
            gyro_scale=np.array(data['gyro_scale']),
        )


class IMUCalibrator:
    def __init__(self, fs: float = 125.0):
        self.fs = fs
    
    def calibrate_static(
        self,
        data: np.ndarray,
        duration: float = 5.0
    ) -> CalibrationParams:
        """
        перед каждой сессией
        
        ИНСТРУКЦИЯ ДЛЯ ПОЛЬЗОВАТЕЛЯ:
        1. Положите устройство на ровную горизонтальную поверхность
        2. Не двигайте устройство 5 секунд
        3. Нажмите "Начать калибровку"
        """
        acc_data = data[:, 2:5]
        gyro_data = data[:, 5:8]
        n_samples = int(duration * self.fs)
        
        acc_static = acc_data[:n_samples]
        gyro_static = gyro_data[:n_samples]
        
        acc_bias = np.mean(acc_static, axis=0)
        acc_bias[2] -= 9.81
        acc_scale = np.ones(3)
        
        gyro_bias = np.mean(gyro_static, axis=0)
        gyro_scale = np.ones(3)
        
        return CalibrationParams(
            acc_bias=acc_bias,
            acc_scale=acc_scale,
            gyro_bias=gyro_bias,
            gyro_scale=gyro_scale
        )
    
    def calibrate_6point(
        self,
        data: np.ndarray
    ) -> CalibrationParams:
        """
        только один раз за весь период
        нужна будет анимация
        
        ИНСТРУКЦИЯ:
        Измерьте ускорение в 6 ориентациях (каждая по 3 секунды):
        1. +X вверх (устройство на правом боку)
        2. -X вверх (устройство на левом боку)
        3. +Y вверх (устройство на переднем торце)
        4. -Y вверх (устройство на заднем торце)
        5. +Z вверх (устройство горизонтально, экран вверх)
        6. -Z вверх (устройство горизонтально, экран вниз)           
        """
        acc_measurements = data[:, 2:5]
        n_samples = len(acc_measurements)
        samples_per_position = n_samples // 6
        
        required_positions = ["+x", "-x", "+y", "-y", "+z", "-z"]
        acc_measurements = {}
        for i, pos in enumerate(required_positions):
            start_idx = i * samples_per_position
            end_idx = start_idx + samples_per_position
            acc_measurements[pos] = acc_measurements[start_idx:end_idx]
        
        means = {}
        for pos, data in acc_measurements.items():
            means[pos] = np.mean(data, axis=0)
        
        acc_bias = np.zeros(3)
        acc_scale = np.ones(3)
        
        g = 9.81  
        for axis in range(3):
            pos_key = ["+x", "+y", "+z"][axis]
            neg_key = ["-x", "-y", "-z"][axis]
            
            pos_val = means[pos_key][axis]
            neg_val = means[neg_key][axis]
            
            acc_bias[axis] = (pos_val + neg_val) / 2

            acc_scale[axis] = (pos_val - neg_val) / (2 * g)
        
        gyro_bias = np.mean(data[:, 5:8], axis=0)
        gyro_scale = np.ones(3)
        
        return CalibrationParams(
            acc_bias=acc_bias,
            acc_scale=acc_scale,
            gyro_bias=gyro_bias,
            gyro_scale=gyro_scale
        )
    
    def apply_calibration(
        self,
        data: np.ndarray,
        params: CalibrationParams,
    ) -> Tuple[np.ndarray, np.ndarray, Optional[np.ndarray]]:
        calibrated_data = data.copy()
        acc_data = data[:, 2:5]
        gyro_data = data[:, 5:8]

        acc_calibrated = (acc_data - params.acc_bias) / params.acc_scale
        gyro_calibrated = (gyro_data - params.gyro_bias) / params.gyro_scale
       
        calibrated_data[:, 2:5] = acc_calibrated
        calibrated_data[:, 5:8] = gyro_calibrated
        
        return calibrated_data