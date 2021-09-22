from scipy.signal.signaltools import sosfilt
import serial
import numpy as np
import matplotlib.pyplot as plt
import sys
from scipy import signal
import time
import io


ser = serial.Serial('COM8', 2*441000)

# try:
#     while True:
#         ser.write(b'z')
#         print(ser.read())
#         time.sleep(1/440)
#         ser.write(b' ')
#         time.sleep(1/440)
# 
# except KeyboardInterrupt:
#     pass

try:
    while True:
        with open("bangarang-44k.wav", mode="rb") as audio:            
                ser.write(audio.read())
except KeyboardInterrupt:
    pass

ser.close()
            
