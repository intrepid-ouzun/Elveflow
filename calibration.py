import sys
import time
import os
import json

from ctypes import *
from pathlib import Path


sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/DLL64')#add the path to Elveflow64.lib here
sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/Python/Python_64')#add the path of the Elveflow64.py

from Elveflow64 import *

# ----- OB1 INITIALIZATION -----
channel_MFS = c_int32(2)
Instr_ID=c_int32(-1) # handle for the SDK communication, increments with each new instrument initialized
error = OB1_Initialization('113433'.encode('ascii'),0,0,0,0,byref(Instr_ID)) 
error = OB1_Add_Sens(Instr_ID.value, channel_MFS, 5, 1, 1, 7, 0) 
print("added Sensor with error", error)

# ----- CALIBRATION FILE SETUP -----
Calib_path = r"C:\Users\oykuz\calibration.txt"

# time stamp the calib file
timestamp = time.strftime("%Y%m%d")
folder, filename = os.path.split(Calib_path)
name, ext = os.path.splitext(filename)

# Create new filename with timestamp
new_filename = f"{name}_{timestamp}{ext}"
new_path = os.path.join(folder, new_filename)
path_buf = create_string_buffer(new_path.encode('ascii'))  # char path[] (array), NUL added automatically


#----- CALIBRATION PROCEDURE -----
    
# ------ > NEW
# start = time.time() # Start timer
# error = OB1_Calib (Instr_ID.value)
# elapsed = time.time() - start
# print ("ran calibration in %d seconds with exit code %d" %(elapsed, error))

# error = OB1_Calib_Save(Instr_ID.value, path_buf)
# print("Saved calibration to %s with error code %d" % (new_path, error))

# ------ > LOAD
error=OB1_Calib_Load (Instr_ID.value, path_buf)

# calibrationDataDouble = (c_double*1000)() #array of 1000 doubles
# Path(new_path).parent.mkdir(parents=True, exist_ok=True)
# with open(new_path, "w", encoding="utf-8", newline="\n") as f:
#     json.dump(calibrationDataDouble, f, ensure_ascii=False)  # ensure_ascii=False keeps non-ASCII if ever needed

# with open(new_path, "rt") as f:
#     calibrationData = json.load(f)
# if len(calibrationData) != 1000:
#     raise ValueError("Calibrationdata in file is misformed: should be list of 1000 elements, not {0} elements".format(len(calibrationData)))

# calibrationDataDouble = (c_double*len(calibrationData))(*calibrationData) #needed for PID control functions

#for i in range(len(calibrationData)):
#    calibrationDataDouble[i] = c_double(calibrationData[i])


#pressure sweep - MFS can only detect flow up to 250 mbar with the current simple setup, ca
# for i in range(-280, 0):
#     error = OB1_Set_Press(Instr_ID.value, channel_MFS, c_double(i))
#     #noticed a bit of offset from the value set here and the pressure value displayed on OB1
#     #eg. i =278 -> display = 222 mbar  //  i = 309 -> display = 252 mbar
#     time.sleep(0.1)  # Add a short delay to allow pressure to stabilize

error = OB1_Set_Press(Instr_ID.value, channel_MFS, c_double(0)) #reset the pressure to 0 at the end of the sweep


# ---- PID CONTROL ---
K_p = 0.09
K_i = 0.003
target_flow = 300 #ul/min,

error = PID_Add_Remote(Instr_ID.value, channel_MFS, Instr_ID.value, channel_MFS, K_p, K_i, 1) 

error = PID_Set_Running_Remote(Instr_ID.value, channel_MFS, c_int32(1)) #start PID control
error = OB1_Set_Sens(Instr_ID.value, channel_MFS, c_double(target_flow)) #set target flow rate
error = PID_Set_Params_Remote(Instr_ID.value, channel_MFS, 1, K_p, K_i) #update PID params if needed


# --- READ SENSOR DATA ---
sensor_readings = (c_double * 50)()
regulator_readings = (c_double * 50)()

for i in range(50):
    sen = c_double()
    reg = c_double()
    err = OB1_Get_Data(
        Instr_ID.value,
        channel_MFS,
        byref(reg),
        byref(sen),
    )
    sensor_readings[i] = sen.value
    regulator_readings[i] = reg.value

# Convert c_double array to Python list
print("Sensor readings (ul/min):", [sensor_readings[i] for i in range(50)])
print("Regulator readings (mbar):", [regulator_readings[i] for i in range(50)])

#TODO: Try a loop to adjust the PI parameters based on the flow recorded, and a better way of recording the readings over a longer period of time
#TODO: once these two are confirmed, add the logic to the MUX code.


error = PID_Set_Running_Remote(Instr_ID.value, channel_MFS, c_int32(0)) #stop PID control
error = OB1_Destructor(Instr_ID.value)



#-301706 error code is related to the naming of the device and when NI MAX cannot validate the device name. try 



