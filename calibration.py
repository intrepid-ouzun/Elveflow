import sys
from _ast import Load
import time

sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/DLL64')#add the path to Elveflow64.lib here
sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/Python/Python_64')#add the path of the Elveflow64.py

from ctypes import *
from array import array
from enum import IntEnum
import json, pathlib

from Elveflow64 import *


Instr_ID=c_int32(-1) # handle for the SDK communication, increments with each new instrument initialized
error = OB1_Initialization('check'.encode('ascii'),0,0,0,0,byref(Instr_ID)) 

error = OB1_Add_Sens(Instr_ID, 1, 5, 1, 1, 7, 0) 
print("added Sensor, %d", error)



#UNCOMMENT TO PERFORM A NEW CALIBRATION AND OVERWRITE THE OLD (UNLESS PATH IS CHANGED)
# start = time.time() # Start timer
# error = OB1_Calib (Instr_ID.value)
# elapsed = time.time() - start
# print ("ran calibration in %d seconds with exit code %d" %(elapsed, error))

# Calib_path = r"C:\Users\oykuz\calib.txt"
# path_buf = create_string_buffer(Calib_path.encode('ascii'))  # char path[] (array), NUL added automatically
# error = OB1_Calib_Save(Instr_ID.value, path_buf)
# print("Saved calibration to %s with error code %d" % (Calib_path, error))


Calib_path = r"C:\Users\oykuz\calib.txt"

# Generate timestamp
timestamp = time.strftime("%Y%m%d_%H%M%S")

# Split original path
folder, filename = os.path.split(Calib_path)
name, ext = os.path.splitext(filename)

# Create new filename with timestamp
new_filename = f"{name}_{timestamp}{ext}"
new_path = os.path.join(folder, new_filename)




#Calibration with Calib buffer of 1000 doubles - TODO test this!! since i need Calib_Buffer for pID control function calls
Calib_buffer = (c_double*1000)() # Always define array this way, calibration should have 1000 elements
start = time.time() # Start timer
error = OB1_Calib (Instr_ID.value, Calib, 1000)
elapsed = time.time() - start
print ("ran calibration in %d seconds with exit code %d" %(elapsed, error))

Calib_path = r"C:\Users\oykuz\calib.txt"
path_buf = create_string_buffer(Calib_path.encode('ascii'))  # char path[] (array), NUL added automatically
error = OB1_Calib_Save(path_buf, byref(Calib_buffer), 1000)
print("Saved calibration to %s with error code %d" % (Calib_path, error))

#Load with Calib_Buffer = TODO test this as well to check if calibration loads
error=Elveflow_Calibration_Load (path_buf, byref(Calib_buffer), 1000)





Calib_path = r"C:\Users\oykuz\calib.txt"
path_buf = create_string_buffer(Calib_path.encode('ascii'))  # char path[] (array), NUL added automatically
# error = OB1_Calib_Load(Instr_ID.value, path_buf)

#pressure sweep - MFS can only detect flow up to 250 mbar with the current simple setup, ca
for i in range(0, 501):
    error = OB1_Set_Press(Instr_ID.value, c_int32(1), c_double(i))
    #noticed a bit of offset from the value set here and the pressure value displayed on OB1
    #eg. i =278 -> display = 222 mbar  //  i = 309 -> display = 252 mbar
    time.sleep(0.1)  # Add a short delay to allow pressure to stabilize

#error = OB1_Set_Press(Instr_ID.value, c_int32(1), c_double(0)) #reset the pressure to 0 at the end of the sweep


# ---- PID CONTROL ---
K_p = 0.05
K_i = 0.003
sensor_channel = c_int32(1)
pressure_channel = c_int32(1)
target_flow = 50 #ul/min

error = PID_Add_Remote(Instr_ID.value, pressure_channel, Instr_ID.value, sensor_channel, K_p, K_i, 1) 

error = OB1_Start_Remote_Measurement(Instr_ID.value, byref(Calib_buffer), 1000)
error = OB1_Set_Remote_Target(Instr_ID.value, pressure_channel, target_flow) 


#check recording and plotting values from the website.


error = OB1_Destructor(Instr_ID.value)



#-301706 error code is related to the naming of the device and when NI MAX cannot validate the device name. try 



