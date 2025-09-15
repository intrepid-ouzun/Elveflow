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
channel_MFS_MUXout = c_int32(4) #channel for MUX output
OB1_Instr_ID=c_int32(-1) # handle for the SDK communication, increments with each new instrument initialized
MUX_DRI_Instr_Id=c_int32(-1)
Answer=(c_char*40)() #for MUX DRI

error = OB1_Initialization('113433_OB1'.encode('ascii'),0,0,0,0,byref(OB1_Instr_ID)) 
error = OB1_Add_Sens(OB1_Instr_ID.value, channel_MFS, 5, 1, 1, 7, 0) 
print(f"added Sensor to channel {channel_MFS.value} with error {error}")
error = OB1_Add_Sens(OB1_Instr_ID.value, channel_MFS_MUXout, 5, 1, 1, 7, 0) 
print(f"added MUX_OUT Sensor to channel {channel_MFS_MUXout.value} with error {error}")



# ----- LOAD CALIBRATION -----
#Calib_path = r"C:\Users\oykuz\calibration.txt"

Calib_path = r"C:\Users\Public\Documents\Elvesys\ESI\bin\48V444400113433.calib" #test loading the config file that SDK generates to see if there is a differenc ein behavior
path_buf = create_string_buffer(Calib_path.encode('ascii'))  # char path[] (array), NUL added automatically
error = OB1_Calib_Load (OB1_Instr_ID.value, path_buf)
error = OB1_Set_Press(OB1_Instr_ID.value, channel_MFS, c_double(0)) #reset the pressure to 0 as a safety measure

error = MUX_DRI_Initialization("12MUX".encode('ascii'),byref(MUX_DRI_Instr_Id))#choose the COM port, it can be ASRLXXX::INSTR (where XXX=port number)
error = MUX_DRI_Send_Command(MUX_DRI_Instr_Id.value, 0, Answer, 40) #0 is for homing the valve which is necessary before using it writes 'Home' to the Answer buffer
print("Homing and initial command sent to MUX with error code", error)
error = MUX_DRI_Send_Command(MUX_DRI_Instr_Id.value, 1, Answer, 40) #0 is for homing the valve which is necessary before using it
print(f"SerialNumber is {Answer.value} with error code", error)
error = MUX_DRI_Set_Valve(MUX_DRI_Instr_Id.value, 1, 1) #last param is rotation: 0 (shortest), 1 (clock), 2 (counterClock)

valve = c_int32(-1)
error = MUX_DRI_Get_Valve(MUX_DRI_Instr_Id.value, byref(valve)) #just to test the sdk function


pressure = 200
error = OB1_Set_Press(OB1_Instr_ID.value, channel_MFS, c_double(pressure)) 



error = MUX_DRI_Set_Valve(MUX_DRI_Instr_Id.value, 2, 0) #last param is rotation: 0 (shortest), 1 (clock), 2 (counterClock)
sen = c_double()
reg = c_double()
error = OB1_Get_Data(OB1_Instr_ID.value, channel_MFS, byref(reg), byref(sen))
error = OB1_Get_Data(OB1_Instr_ID.value, channel_MFS_MUXout, byref(reg), byref(sen))

#CHANGE THE PRESSURE TO SEE IF YOU GET A DIFFERENT READING
error = OB1_Set_Press(OB1_Instr_ID.value, channel_MFS, c_double(pressure)) 
error = MUX_DRI_Set_Valve(MUX_DRI_Instr_Id.value, 3, 2) #last param is rotation: 0 (shortest), 1 (clock), 2 (counterClock)
error = OB1_Get_Data(OB1_Instr_ID.value, channel_MFS, byref(reg), byref(sen))
error = OB1_Get_Data(OB1_Instr_ID.value, channel_MFS_MUXout, byref(reg), byref(sen))

error = OB1_Set_Press(OB1_Instr_ID.value, channel_MFS, c_double(0)) #reset the pressure to 0 as a safety measure

#now start PI control loop
K_p = 0.001
K_i = 0.001
target_flow = 300 #ul/min,

error = PID_Add_Remote(OB1_Instr_ID.value, channel_MFS, OB1_Instr_ID.value, channel_MFS, K_p, K_i, 1) 

error = PID_Set_Running_Remote(OB1_Instr_ID.value, channel_MFS, c_int32(1)) #start PID control
error = OB1_Set_Sens(OB1_Instr_ID.value, channel_MFS, c_double(target_flow)) #set target flow rate
error = PID_Set_Params_Remote(OB1_Instr_ID.value, channel_MFS, 1, K_p, K_i) #update PID params if needed

#Technically this loop should automatically adjust the pressure levels to maintain the flow we need.

#end remote PID, set pressure to 0 and switch valve.
error = PID_Set_Running_Remote(OB1_Instr_ID.value, channel_MFS, c_int32(0)) #stop PID control
error = OB1_Set_Press(OB1_Instr_ID.value, channel_MFS, c_double(0)) #reset the pressure to 0 as a safety measure



error = MUX_DRI_Destructor(MUX_DRI_Instr_Id.value)
error = OB1_Destructor(OB1_Instr_ID.value)




