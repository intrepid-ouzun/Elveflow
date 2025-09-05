import sys
from email.header import UTF8
sys.path.append('D:/dev/SDK/DLL32/DLL32')#add the path of the library here
sys.path.append('D:/dev/SDK/Python_32')#add the path of the LoadElveflow.py

from array import array
from ctypes import *
from enum import IntEnum
import json, pathlib

from Elveflow32 import *

from enum import IntEnum


# OB1 we got has all its channels set to (-900,1000) mbar, which corresponds to Z_regulator_type = 4 (-1000, 1000) range from manual
# for the MFS we ordered, the Z_sensor_type is 5 since the range is 0-1000uL
# the resolution from MFS sensor is up to 16 bits since it uses I2C communication, can specify what to read when adding a sensor

#OB1 constants
REGULATOR_TYPE = 4
CALIB_LEN = 1000 #length of the calibration table for OB1 is always 1000

#MFS constants
H20_CALIBRATION = 0
IPA_CALIBRATION = 1
SENSOR_TYPE = 5
MFS_RESOLUTION = 7 #[0, 7] corresponds to [9, 16] bits

Instr_ID = c_int32(-1)

# error codes from the end of the SDK User Guide - probably won't need all of them
# more error codes can be found: https://www.ni.com/docs/en-US/bundle/labview-api-ref/page/errors/general-labview-error-codes.html
class ErrorCode(IntEnum):
    NO_DIGITAL_SENSOR                      = 8000
    NO_PRESSURE_SENSOR_OB1_MK3             = 8001
    NO_DIGITAL_PRESSURE_SENSOR_MK3_PLUS    = 8002
    NO_DIGITAL_FLOW_SENSOR_MK3             = 8003
    NO_IPA_CONFIG_FOR_SENSOR               = 8004
    SENSOR_NOT_COMPATIBLE                  = 8005
    NO_INSTRUMENT_WITH_SELECTED_ID         = 8006
    WRONG_MUX_DEVICE                       = 8007
    ONLY_AVAILABLE_FOR_MUX_WIRE_V3         = 8008
    VALVE_TYPE_RESERVED_FOR_V3_USE_4_5_6   = 8009
    NO_COMMUNICATION_WITH_OB1              = 8030
    NO_COMMUNICATION_WITH_BFS              = 8031
    NO_COMMUNICATION_WITH_MSRD             = 8032
    OB1_REMOTE_LOOP_NOT_EXECUTED           = 8033
    BFS_REMOTE_LOOP_NOT_EXECUTED           = 8034
    MSRD_REMOTE_LOOP_NOT_EXECUTED          = 8035

ERROR_MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.NO_DIGITAL_SENSOR:                    "No Digital Sensor found",
    ErrorCode.NO_PRESSURE_SENSOR_OB1_MK3:           "No pressure sensor compatible with OB1 MK3",
    ErrorCode.NO_DIGITAL_PRESSURE_SENSOR_MK3_PLUS:  "No Digital pressure sensor compatible with OB1 MK3+",
    ErrorCode.NO_DIGITAL_FLOW_SENSOR_MK3:           "No Digital Flow sensor compatible with OB1 MK3",
    ErrorCode.NO_IPA_CONFIG_FOR_SENSOR:             "No IPA config for this sensor",
    ErrorCode.SENSOR_NOT_COMPATIBLE:                "Sensor not compatible",
    ErrorCode.NO_INSTRUMENT_WITH_SELECTED_ID:       "No Instrument with selected ID",
    ErrorCode.WRONG_MUX_DEVICE:                     "Wrong MUX device",
    ErrorCode.ONLY_AVAILABLE_FOR_MUX_WIRE_V3:       "Only available for MUX Wire V3 devices",
    ErrorCode.VALVE_TYPE_RESERVED_FOR_V3_USE_4_5_6: "Types 1, 2, 3 are reserved for V3 valves; use 4, 5, or 6 for custom/older valves",
    ErrorCode.NO_COMMUNICATION_WITH_OB1:            "No communication with OB1",
    ErrorCode.NO_COMMUNICATION_WITH_BFS:            "No communication with BFS",
    ErrorCode.NO_COMMUNICATION_WITH_MSRD:           "No communication with MSRD",
    ErrorCode.OB1_REMOTE_LOOP_NOT_EXECUTED:         "OB1 remote loop has not been executed",
    ErrorCode.BFS_REMOTE_LOOP_NOT_EXECUTED:         "BFS remote loop has not been executed",
    ErrorCode.MSRD_REMOTE_LOOP_NOT_EXECUTED:        "MSRD remote loop has not been executed",
}

def _raise_if_error(code: int, where: str):
    if isinstance(code, int) and code != 0:
        try:
            msg = ERROR_MESSAGES[ErrorCode(code)]
        except Exception:
            msg = f"Unrecognized error code {code}"
        raise RuntimeError(f"{where}: {msg} (code {code})")
    
    
def initializeOB1(deviceName: str):
    
    """
        Initialize OB1 and return its Instrument ID.
        deviceName: e.g. '01CF6A61' (from ESI / NI-MAX)
        regulator1...4: regulator codes per channel (int)
    """
    
    global Instr_ID 
    Instr_ID = c_int32()
    error = OB1_Initialization(deviceName.encode('ascii'), REGULATOR_TYPE, REGULATOR_TYPE, REGULATOR_TYPE, REGULATOR_TYPE, byref(Instr_ID)) 
    print(f"initializeOB1 -> error: {error}, OB1 ID: {Instr_ID.value}")
    _raise_if_error(error, "OB1_Initialization")
    return Instr_ID.value

def closeOB1():
    global Instr_ID
    if Instr_ID.value >= 0:
        error = OB1_Destructor(Instr_ID.value)
        _raise_if_error(error, "OB1_Destructor")
        Instr_ID.value = -1
        print("OB1 closed.")
        return 0
    
def addSensor(channel: int, calibration: int=IPA_CALIBRATION, resolution: int=MFS_RESOLUTION):     
    global Instr_ID
    error = OB1_Add_Sens(Instr_ID, channel, SENSOR_TYPE, 1, calibration, resolution, 0) #voltage level?
    #For digital sensors, the sensor type is automatically detected during this function call.
    
    #print(f'OB1_addSensor -> error: {error}')
    _raise_if_error(error, "OB1: addSensor")

def performCaibration(path: str):
    OB1_Calib (Instr_ID.value)
    error = OB1_Calib_Save(path.value, path.encode('ascii'))
    print(f'calib saved in {path}')
    #print(f'OB1_performCalibration -> error: {error}')
    _raise_if_error(error, "OB1: performCalibration")

    
def loadCalibration(path: str):
    """
    Load calibration from a JSON file into the 1000-double buffer.
    JSON must contain a list of 1000 floats.
    """
    
    calibration_path = pathlib.Path(path)
    
    #error checking
    if not calibration_path.exists():
        raise FileNotFoundError(f"No calibration file at '{calibration_path}'")
    with calibration_path.open("r", encoding="utf-8") as f:
        data = json.load(f)  
    if not isinstance(data, list) or len(data) != CALIB_LEN:
        raise ValueError(f"Calibration JSON must have {CALIB_LEN} numbers, got {len(data)}")
    
    error = OB1_Calib_Load(Instr_ID.value, calibration_path.encode('ascii'))
    #print(f"OB1_loadCalibration -> error: {error}").strip()
    _raise_if_error(error, "OB1: loadCalibration")
    
    
def setPressure(channel: int, pressure: float = 0):
    
    if (pressure < -900 or pressure > 1000):
        print("Outside the pressure range of [-900,1000] mbar")
        return -1
    
    error = OB1_Set_Press(Instr_ID.value, c_int32(channel), c_double(pressure)) 
    #print(f"OB1_setPressure -> error: {error}").strip()
    _raise_if_error(error, "OB1: setPressure")

def readMFS(instrID: int, channel: int):
    regulatorData = c_double()
    sensorData = c_double()
    
    error = OB1_Get_Data(instrID, channel, byref(regulatorData), byref(sensorData))
    if error != 0:
        raise RuntimeError(f"OB1_Get_Data error: {error}")
    return regulatorData.value, sensorData.value
    

def feed
#PID feedbck function / depositing a certain volmume function
    
#keep adding working loop functions to test  
    
    
def main():
    
   #typical workflow would be initialize -> addSensor -> calibrate (perform, load) -> working loop -> closeOB
   deviceName = '01CF6A61' 
   path = "" # path to save the calibration file to
   
   initializeOB1(deviceName)
   #addSensor(1) #if we want to add the MFS to ch1
   performCaibration(path)
   
   
   

if __name__ == "__main__":
    main()
