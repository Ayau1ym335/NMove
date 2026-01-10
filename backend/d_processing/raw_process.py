import numpy as np
import struct
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import logging
from pathlib import Path

from calibration import CalibrationParams, IMUCalibrator
from lowp_f import prefiltration, SegmentedAdaptiveFilter, FILTER_CONFIGS
from madgwick import MadgwickAHRS
from step_detection import GaitEventDetector
from .quaternion import Quaternion

@dataclass
class ProcessingConfig:
    """Configuration for the processing pipeline"""
    sampling_rate: int = 125  # Hz
    calibration_duration: int = 5  # seconds
    activity_threshold: float = 0.5
    filter_cutoff: float = 25.0  # Hz
    madgwick_beta: float = 0.1
    min_session_duration: float = 5.0  # seconds
    step_detection_threshold: float = 1.5  # g-force
    def get_lab_params(self) -> Optional[CalibrationParams]:
        import json
        import os
        path = "calibration_lab.json"
        if os.path.exists(path):
            with open(path, 'r') as f:
                return CalibrationParams.from_dict(json.load(f))
        return None 

@dataclass
class ProcessedData:
    """Container for processed data at each stage"""
    raw_imu: Optional[np.ndarray] = None
    calibrated: Optional[np.ndarray] = None
    prefiltered: Optional[np.ndarray] = None
    activity: Optional[List[Dict[str, Any]]] = None
    filtered: Optional[np.ndarray] = None
    orientation: Optional[np.ndarray] = None  
    step_events: Optional[List[Dict]] = None
    error_message: Optional[str] = None

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

class GaitProcessingPipeline:
    def __init__(self, config: Optional[ProcessingConfig] = None):
        self.config = config or ProcessingConfig()
        self.logger = self._setup_logger()

        self.unpacking = unpack_bin
        self.calibration = IMUCalibrator()
        self.prefilter = prefiltration
        self.filter = SegmentedAdaptiveFilter()
        self.madgwick = MadgwickAHRS()
        self.step_detector = GaitEventDetector()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        return logger

    def process_session(self, bin_file_path: str) -> ProcessedData:
        result = ProcessedData()
        
        try:
            self.logger.info(f"Stage 1")
            raw_data = self._process_raw_data(bin_file_path)
            if raw_data is None:
                result.error_message = "Failed to read raw binary data"
                return result
            result.raw_imu = raw_data
            
            self.logger.info("Stage 2")
            calibrated_data = self._apply_calibration(raw_data)
            if calibrated_data is None:
                result.error_message = "Calibration failed"
                return result
            result.calibrated = calibrated_data
            
            self.logger.info("Stage 3")
            prefiltered_data = self._apply_prefiltration(calibrated_data)
            if prefiltered_data is None:
                result.error_message = "Pre-filtration failed"
                return result
            result.prefiltered = prefiltered_data
        
            self.logger.info("Stage 4")
            filtered_data, activity = self._apply_filtration(prefiltered_data)
            if filtered_data is None:
                result.error_message = "Main filtration failed"
                return result
            result.filtered = filtered_data
            result.activity = activity
            
            self.logger.info("Stage 5")
            orientation = self._compute_orientation(filtered_data)
            if orientation is None:
                result.error_message = "Orientation computation failed"
                return result
            result.orientation = orientation
        
            self.logger.info("Stage 6")
            step_events = self._detect_steps(filtered_data, orientation)
            result.step_events = step_events
            
        except Exception as e:
            self.logger.error(f"Pipeline error: {str(e)}", exc_info=True)
            result.error_message = f"Pipeline error: {str(e)}"
            result.is_valid = False
            
        return result
    
    def _process_raw_data(self, bin_file_path: str) -> Optional[np.ndarray]:
        try:
            if not Path(bin_file_path).exists():
                self.logger.error(f"Binary file not found: {bin_file_path}")
                return None
                
            raw_data = self.unpacking(bin_file_path)
            
            if raw_data is None or len(raw_data) == 0:
                self.logger.error("Raw data is empty")
                return None
            
            if raw_data.shape[1] != 8:
                self.logger.error(f"Invalid data shape: {raw_data.shape}")
                return None
                
            return raw_data
            
        except Exception as e:
            self.logger.error(f"Raw data processing error: {e}")
            return None
    
    def _apply_calibration(self, raw_data: np.ndarray) -> Optional[np.ndarray]:
        try:
            fresh_static = self.calibration.calibrate_static(raw_data)
            lab_params = self.config.get_lab_params() 
            final_params = self.calibration.merge_calibration(fresh_static, lab_params)
            self.calibration.set_params(final_params)
            return self.calibration.apply_calibration(raw_data)
        except Exception as e:
            self.logger.error(f"Calibration error: {e}")
            return None
    
    def _apply_prefiltration(self, calibrated_data: np.ndarray) -> Optional[np.ndarray]:
        try:
            prefiltered = self.prefilter(calibrated_data)
            return prefiltered  
        except Exception as e:
            self.logger.error(f"Pre-filtration error: {e}")
            return None
    
    def _apply_filtration(self, prefiltered_data: np.ndarray):
        try:
            filtered, activity = self.filter.filter_segmented(prefiltered_data)
            return filtered, activity
            
        except Exception as e:
            self.logger.error(f"Filtration error: {e}")
            return None
    
    def _compute_orientation(self, filtered_data: np.ndarray) -> Optional[np.ndarray]:
        try:
            acc = filtered_data[:, 2:5]
            gyro = filtered_data[:, 5:8]
            self.madgwick.quaternion = Quaternion(1, 0, 0, 0)
            orientations = []
            for i in range(len(filtered_data)):
                quat = self.madgwick.update_imu(acc[i], gyro[i])
                rpy = self._quaternion_to_euler(quat)
                orientations.append(rpy)
                
            return np.array(orientations)
            
        except Exception as e:
            self.logger.error(f"Orientation computation error: {e}")
            return None
    
    def _detect_steps(self, filtered_data: np.ndarray) -> List[Dict[str, int]]:
        try:
           steps = self.step_detector.detect(filtered_data)
           return steps
        except Exception as e:
            self.logger.error(f"Step detection error: {e}")
            return []

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