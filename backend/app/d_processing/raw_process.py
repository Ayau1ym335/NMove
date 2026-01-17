import numpy as np
from typing import Optional
from dataclasses import dataclass, field
import json
import os
import datetime

from .unpacking import unpack_bin
from .imu_calibration import Calibrator
from .lowp_f import prefiltration, Filter 
from .madgwick import MadgwickAHRS
from .step_detection import StepDetector
from .quaternion import Quaternion
from .detect_act import ActivityDetector
from .step_pro import calculate_step_metrics
from .session_pro import calculate_session_summary
from .dclass import Metadata

def quaternion_to_euler(q: np.ndarray) -> np.ndarray:
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

class GaitAnalysisOrchestrator:
    def __init__(
        self,
        unpack_bin= None,
        calibrator=Calibrator(),
        prefiltration= None,
        activity_detector=ActivityDetector(),
        filter=Filter(),
        event_detector=StepDetector(),
        calculate_step_metrics= None,
        session = None,
        sampling_rate: int = 125
    ):
        self.unpacking = unpack_bin
        self.calibrator = calibrator
        self.prefiltration = prefiltration
        self.activity_detector = activity_detector
        self.filter = filter
        self.event_detector = event_detector
        self.calculate_step_metrics = calculate_step_metrics
        self.session = session
        self.sampling_rate = sampling_rate
        self.dt = 1.0 / sampling_rate
        
        self.madgwick_thigh = MadgwickAHRS(sampleperiod=self.dt, beta=0.1)
        self.madgwick_shank = MadgwickAHRS(sampleperiod=self.dt, beta=0.1)
    
    def process_session(self, raw_data: np.ndarray, metadata):
        device_id = os.path.splitext(raw_data)[0]
        try:
            unpacked = self.unpacking(raw_data)
        except Exception as e:
            unpacked = raw_data
            return ' Have an error: {e}'
        
        try:
            self.calibrator.load(device_id)
            self.calibrator.align_to_gravity(unpacked)
            calibrated = self.calibrator.apply(unpacked)
        except Exception as e:
            calibrated = unpacked
            return ' Have an error: {e}'
        
        try:
            prefiltrated = self.prefiltration(calibrated)
        except Exception as e:
            prefiltrated = calibrated
            return ' Have an error: {e}'
        
        try:
            activities = self.activity_detector.detect(prefiltrated)
        except Exception as e:
            activities = []
            return ' Have an error: {e}'
        
        try:
            filtrated = self.filter.process(prefiltrated, activities)
        except Exception as e:
            filtrated = prefiltrated
            return ' Have an error: {e}'
        
        try:
            cycles, orientations = self.orientation(filtrated)
        except Exception as e:
            cycles, orientations = []
            return ' Have an error: {e}'
        
        try:
            metrics_list = self.calculate_step_metrics(filtrated, orientations, cycles)
        except Exception as e:
            return ' Have an error: {e}'
        
        try:
            session_summary = self.session.calculate_session_summary(metrics_list, orientations, activities, metadata)
        except Exception as e:
            return ' Have an error: {e}'

        

    def orientation(self, filtrated: np.ndarray):
        n = len(filtrated)
        orientations = np.zeros(n, dtype=[('thigh_pitch', 'f4'), ('shank_pitch', 'f4'), ('knee_angle', 'f4')])
        acc_vertical = np.zeros(n)
        gyro_shank_rad = np.deg2rad(filtrated['gyro2'])
        sag_idx = np.argmax(np.std(gyro_shank_rad, axis=0))
        gyro_sagittal = filtrated['gyro2'][:, sag_idx]

        for i in range(n):
            self.madgwick_thigh.update_imu(np.deg2rad(filtrated['gyro1'][i]), filtrated['acc1'][i])
            t_pitch = np.rad2deg(self.madgwick_thigh.quaternion.to_euler_angles()[1]) 
        
            self.madgwick_shank.update_imu(gyro_shank_rad[i], filtrated['acc2'][i])
            q_s = self.madgwick_shank.quaternion.q
            s_pitch = np.rad2deg(self.madgwick_shank.quaternion.to_euler_angles()[1])
        
            ax, ay, az = filtrated['acc2'][i]
            w, x, y, z = q_s
            z_global = (ax * (2*x*z + 2*w*y) + ay * (2*y*z - 2*w*x) + az * (1 - 2*x**2 - 2*y**2))
            acc_vertical[i] = z_global - 9.81
        
            orientations[i]['thigh_pitch'] = t_pitch
            orientations[i]['shank_pitch'] = s_pitch
            orientations[i]['knee_angle'] = t_pitch - s_pitch

        cycles = self.event_detector.detect_cycles(gyro_sagittal, acc_vertical, filtrated['timestamp'])
        return cycles, orientations
  