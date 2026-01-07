
import numpy as np
from scipy.signal import butter, filtfilt
import matplotlib.pyplot as plt

# Filter parameters
cutoff_freq = 100  # Cutoff frequency in Hz
fs = 1000  # Sampling rate in Hz
order = 4  # Filter order

# Design the low-pass filter
nyq = 0.5 * fs
normal_cutoff = cutoff_freq / nyq
b, a = butter(order, normal_cutoff, btype='lowpass')

# Sample data (with time vector)
t = np.linspace(0, 1, 1000)  # Time vector for 1 second signal
data = np.sin(2*np.pi*150*t) + np.random.rand(1000)  # Example signal with noise

# Apply the filter
filtered_data = filtfilt(b, a, data)

# Plot the original and filtered data
plt.figure(figsize=(10, 6))

plt.plot(t, data, label='Original Signal')
plt.plot(t, filtered_data, label='Filtered Signal')

plt.xlabel('Time (s)')
plt.ylabel('Amplitude')
plt.title('Low-Pass Filtering Example')
plt.legend()
plt.grid(True)

plt.show()
