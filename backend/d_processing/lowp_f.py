import numpy as np
from scipy.signal import butter, filtfilt

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





