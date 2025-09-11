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
OB1_Instr_ID=c_int32(-1) # handle for the SDK communication, increments with each new instrument initialized
MUX_DRI_Instr_Id=c_int32(-1)
Answer=(c_char*40)() #for MUX DRI

error = OB1_Initialization('113433'.encode('ascii'),0,0,0,0,byref(Instr_ID)) 
error = OB1_Add_Sens(Instr_ID.value, channel_MFS, 5, 1, 1, 7, 0) 
print(f"added Sensor to channel {channel_MFS} with error {error}")


# ----- LOAD CALIBRATION -----
Calib_path = r"C:\Users\oykuz\calibration.txt"
#defaultCalib_path = r"C:\Users\Public\Documents\Elvesys\ESI\data" #test loading the config file that SDK generates to see if there is a differenc ein behavior
path_buf = create_string_buffer(Calib_path.encode('ascii'))  # char path[] (array), NUL added automatically
error = OB1_Calib_Load (Instr_ID.value, path_buf)
error = OB1_Set_Press(Instr_ID.value, channel_MFS, c_double(0)) #reset the pressure to 0 as a safety measure

error = MUX_DRI_Initialization("ASRL4::INSTR".encode('ascii'),byref(MUX_DRI_Instr_ID))#choose the COM port, it can be ASRLXXX::INSTR (where XXX=port number)

error = MUX_Set_Valve(MUX_DRI_Instr_Id.value, 1, 1) #last param is rotation: 0 (shortest), 1 (clock), 2 (counterClock)
error = MUX_DRI_Send_Command(MUX_DRI_Instr_Id.value, 0, Answer, 40) #0 is for homing the valve which is necessary before using it

valve = c_int32(-1)
error = MUX_Get_Valve(MUX_DRI_Instr_Id.value, byref(valve)) #just to test the sdk function


#now start PI control loop
K_p = 0.09
K_i = 0.003
target_flow = 300 #ul/min,

error = PID_Add_Remote(Instr_ID.value, channel_MFS, Instr_ID.value, channel_MFS, K_p, K_i, 1) 

error = PID_Set_Running_Remote(Instr_ID.value, channel_MFS, c_int32(1)) #start PID control
error = OB1_Set_Sens(Instr_ID.value, channel_MFS, c_double(target_flow)) #set target flow rate
error = PID_Set_Params_Remote(Instr_ID.value, channel_MFS, 1, K_p, K_i) #update PID params if needed

#Technically this loop should automatically adjust the pressure levels to maintain the flow we need.

#end remote PID, set pressure to 0 and switch valve.
error = PID_Set_Running_Remote(Instr_ID.value, channel_MFS, c_int32(0)) #stop PID control
error = OB1_Set_Press(Instr_ID.value, channel_MFS, c_double(0)) #reset the pressure to 0 as a safety measure


error = MUX_Set_Valve(MUX_DRI_Instr_Id.value, 2, 1) #last param is rotation: 0 (shortest), 1 (clock), 2 (counterClock)
error = MUX_DRI_Send_Command(MUX_DRI_Instr_Id.value, 0, Answer, 40) #0 is for homing the valve which is necessary before using it

error = MUX_Get_Valve(MUX_DRI_Instr_Id.value, byref(valve)) #just to test the sdk function

error = PID_Set_Running_Remote(Instr_ID.value, channel_MFS, c_int32(1)) #start PID control
target_flow = 500
error = OB1_Set_Sens(Instr_ID.value, channel_MFS, c_double(target_flow)) #set target flow rate
error = PID_Set_Params_Remote(Instr_ID.value, channel_MFS, 1, K_p, K_i) #update PID params if needed

#potentially add code here to record pressure and sensor readings




error=MUX_DRI_Destructor(MUX_DRI_Instr_ID.value)
error = OB1_Destructor(Instr_ID.value)




