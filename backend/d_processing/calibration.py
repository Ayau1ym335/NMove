import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from raw_process import unpack_bin
import json 

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

def run_lab_calibration(bin_file_path: str):
    try:
        raw_data = unpack_bin(bin_file_path)
    except Exception as e:
        print(f"Error: {e}")
        return

    calibrator = IMUCalibrator()
    lab_params = calibrator.calibrate_6point(raw_data)
    output_file = "calibration_lab.json"
    try:
        params_dict = lab_params.to_dict()
        with open(output_file, 'w') as f:
            json.dump(params_dict, f, indent=4)
        
    except Exception as e:
        print(f"Error: {e}")
        return

class IMUCalibrator:
    def __init__(self, fs: float = 125.0):
        self.fs = fs
        self.current_params: Optional[CalibrationParams] = None

    def set_params(self, params: CalibrationParams):
        self.current_params = params

    def merge_calibration(self, static_params: CalibrationParams, lab_params: Optional[CalibrationParams] = None) -> CalibrationParams:
        if lab_params is None:
            return static_params
            
        return CalibrationParams(acc_bias=static_params.acc_bias, acc_scale=lab_params.acc_scale,
        gyro_bias=static_params.gyro_bias,gyro_scale=lab_params.gyro_scale)
    
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

    def calibrate_6point(self, data: np.ndarray) -> CalibrationParams:
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
        acc_raw = data[:, 2:5]
        gyro_raw = data[:, 5:8]
    
        n_samples = len(acc_raw)
        samples_per_pos = n_samples // 6
        g = 9.81
    
        required_positions = ["+x", "-x", "+y", "-y", "+z", "-z"]
        means = {}
    
        for i, pos in enumerate(required_positions):
           chunk = acc_raw[i * samples_per_pos : (i + 1) * samples_per_pos]
           means[pos] = np.mean(chunk, axis=0)
    
        acc_bias = np.zeros(3)
        acc_scale = np.ones(3)
    
        for i in range(3):
           pos_val = means[required_positions[i*2]][i]     
           neg_val = means[required_positions[i*2 + 1]][i] 
        
           acc_bias[i] = (pos_val + neg_val) / 2
           acc_scale[i] = (pos_val - neg_val) / (2 * g)
        
        gyro_bias = np.mean(gyro_raw, axis=0)
    
        return CalibrationParams(acc_bias=acc_bias,acc_scale=acc_scale,gyro_bias=gyro_bias,gyro_scale=np.ones(3))

    def apply_calibration(self,data: np.ndarray) -> np.ndarray:
        if self.current_params is None:
            return data
        params = self.current_params
        calibrated_data = data.copy()
        acc_data = data[:, 2:5]
        gyro_data = data[:, 5:8]

        acc_calibrated = (acc_data - params.acc_bias) / params.acc_scale
        gyro_calibrated = (gyro_data - params.gyro_bias) / params.gyro_scale
       
        calibrated_data[:, 2:5] = acc_calibrated
        calibrated_data[:, 5:8] = gyro_calibrated
        
        return calibrated_data