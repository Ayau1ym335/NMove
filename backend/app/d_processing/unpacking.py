import numpy as np
def unpack_bin(file_path):
    dt = np.dtype([
        ('header', 'u1'),
        ('timestamp', 'f8'),
        ('acc1',      'f4', (3,)), # x, y, z thigh 
        ('gyro1',     'f4', (3,)), # x, y, z
        ('acc2',      'f4', (3,)), # x, y, z shin
        ('gyro2',     'f4', (3,))  # x, y, z
    ])
    data = np.fromfile(file_path, dtype=dt)
    return data