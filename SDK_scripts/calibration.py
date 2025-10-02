import sys
import time
import os
import json

from ctypes import *
from pathlib import Path
from collections import deque   # <-- add this line
import numpy as np              # <-- add this line
import pandas as pd             # <-- add this line 
import matplotlib.pyplot as plt
from datetime import datetime


sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/DLL64')#add the path to Elveflow64.lib here
sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/Python/Python_64')#add the path of the Elveflow64.py

from Elveflow64 import *

# ----- OB1 INITIALIZATION -----
channel_MFS = c_int32(2)
Instr_ID=c_int32(-1) # handle for the SDK communication, increments with each new instrument initialized
error = OB1_Initialization('113433'.encode('ascii'),0,0,0,0,byref(Instr_ID)) 
error = OB1_Add_Sens(Instr_ID.value, channel_MFS.value, 5, 1, 1, 7, 0) 
print("added Sensor with error", error)

# ----- CALIBRATION FILE SETUP -----
#Calib_path = r"C:\Users\oykuz\calibration.calib"
Calib_path = r"C:\Users\oykuz\calibration_20250912.CALIB"


#time stamp the calib file
# timestamp = time.strftime("%Y%m%d")
# folder, filename = os.path.split(Calib_path)
# name, ext = os.path.splitext(filename)

# # Create new filename with timestamp
# new_filename = f"{name}_{timestamp}{ext}"
# new_path = os.path.join(folder, new_filename)
# path_buf = create_string_buffer(new_path.encode('ascii'))  # char path[] (array), NUL added automatically


#----- CALIBRATION PROCEDURE -----
    
# ------ > NEW
# start = time.time() # Start timer
# error = OB1_Calib (Instr_ID.value)
# elapsed = time.time() - start
# print ("ran calibration in %d seconds with exit code %d" %(elapsed, error))

# error = OB1_Calib_Save(Instr_ID.value, path_buf)
# print("Saved calibration to %s with error code %d" % (new_path, error))

# ------ > LOAD
# path_buf = "C:\\Users\\Public\\Documents\\Elvesys\\ESI\\bin\\48V444400113433.calib"
error=OB1_Calib_Load (Instr_ID.value, Calib_path.encode('ascii'))
error = OB1_Set_Press(Instr_ID.value, channel_MFS, c_double(0)) #reset the pressure to 0 at the end of the sweep


# # ---- BASIC PID CONTROL ---
# target_flow = -50  # µL/min --> THIS SETS THE PRESSURE TO BE -50 NOT THE FLOWRATE
# K_p = 0.001
# K_i = 0.001 # testerd higher P and I values - they are too noisy.

# # --- INITIALIZE REMOTE PID ---
# err = PID_Add_Remote(Instr_ID.value, channel_MFS, Instr_ID.value, channel_MFS, K_p, K_i, 1)

# err = PID_Set_Running_Remote(Instr_ID.value, channel_MFS, c_int32(1))  # start PID
# err = OB1_Set_Sens(Instr_ID.value, channel_MFS, c_double(target_flow))  # target flow
# err = PID_Set_Params_Remote(Instr_ID.value, channel_MFS, 1, K_p, K_i)   # initial PID params

# #RESET PRESSURE
# error = OB1_Set_Press(Instr_ID.value, channel_MFS, c_double(0)) #reset the pressure to 0 at the end of the sweep


# --- SQUARE WAVEFORM PID FLOW CONTROL ---

flow_low = -50.0   # µL/min
flow_high = 50.0  # µL/min
period_s = 30.0     # full square-wave period (sec)
n_cycles = 5       # number of cycles to run
sample_dt = 0.3    # sample interval (sec)

K_p = 0.001
K_i = 0.001
err = PID_Add_Remote(Instr_ID.value, channel_MFS,
                     Instr_ID.value, channel_MFS,
                     K_p, K_i, 1)

err = PID_Set_Running_Remote(Instr_ID.value, channel_MFS, c_int32(1))  # start PID
err = PID_Set_Params_Remote(Instr_ID.value, channel_MFS, 1, K_p, K_i) # to change p and i paramters

# --- BUFFERS ---
time_log = []
target_log = []
flow_log = []
regulator_log = []

# --- SQUARE-WAVE EXECUTION ---
try:
    n_samples = int(n_cycles * period_s / sample_dt)
    half_period = period_s / 2.0

    t0 = time.time()
    for i in range(n_samples):
        t = time.time() - t0

        # decide square-wave setpoint
        cycle_time = t % period_s
        if cycle_time < half_period:
            target_flow = flow_low
        else:
            target_flow = flow_high

        # update setpoint on OB1
        err = OB1_Set_Sens(Instr_ID.value, channel_MFS, c_double(target_flow))

        # read data
        sen = c_double()
        reg = c_double()
        _ = OB1_Get_Data(Instr_ID.value, channel_MFS, byref(reg), byref(sen))

        # log
        time_log.append(t)
        target_log.append(target_flow)
        flow_log.append(sen.value)
        regulator_log.append(reg.value)

        time.sleep(sample_dt)

finally:
    # always reset and stop PID safely
    _ = OB1_Set_Press(Instr_ID.value, channel_MFS, c_double(0))
    _ = PID_Set_Running_Remote(Instr_ID.value, channel_MFS, c_int32(0))

# --- ANALYZE + PLOT ---
df = pd.DataFrame({
    "time_s": time_log,
    "target_flow": target_log,
    "sensor_flow": flow_log,
    "regulator_mbar": regulator_log,
})

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
csv_path = f"square_flow_log_{timestamp}.csv"
plot_path = f"square_flow_plot_{timestamp}.png"

df.to_csv(csv_path, index=False)
print(f"Data saved to {csv_path}")

plt.figure()
plt.plot(df["time_s"], df["sensor_flow"], label="Measured flow")
plt.plot(df["time_s"], df["target_flow"], "--", label="Target flow")
plt.xlabel("Time [s]")
plt.ylabel("Flow [µL/min]")
plt.legend()
plt.title("Square Wave Flow Control")
plt.savefig(plot_path, dpi=300)
print(f"Plot saved to {plot_path}")

plt.show()

# # --- READ SENSOR DATA ---
# sensor_readings = (c_double * 50)()
# regulator_readings = (c_double * 50)()

# for i in range(50):
#     sen = c_double()
#     reg = c_double()
#     err = OB1_Get_Data(
#         Instr_ID.value,
#         channel_MFS,
#         byref(reg),
#         byref(sen),
#     )
#     sensor_readings[i] = sen.value
#     regulator_readings[i] = reg.value

# # Convert c_double array to Python list
# print("Sensor readings (ul/min):", [sensor_readings[i] for i in range(50)])
# print("Regulator readings (mbar):", [regulator_readings[i] for i in range(50)])

# #TODO: once these two are confirmed, add the logic to the MUX code.


# error = PID_Set_Running_Remote(Instr_ID.value, channel_MFS, c_int32(0)) #stop PID control
# error = OB1_Destructor(Instr_ID.value)






