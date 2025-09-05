import importlib
import json
import pathlib
import sys
from ctypes import byref, c_double, c_int32
from dataclasses import dataclass
from enum import IntEnum
from typing import Tuple
import os

from Elveflow32 import *

#sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/DLL64')#add the path to Elveflow64.lib here
#sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/Python/Python_64')#add the path of the Elveflow64.py


# -----------------------------
# Constants & enums
# -----------------------------


# OB1 we got has all its channels set to (-900,1000) mbar, which corresponds to Z_regulator_type = 4 (-1000, 1000) range from manual
# for the MFS we ordered, the Z_sensor_type is 5 since the range is 0-1000uL
# the resolution from MFS sensor is up to 16 bits since it uses I2C communication, can specify what to read when adding a sensor

#OB1 constants
REGULATOR_TYPE = 4
CALIB_LEN = 1000 #length of the calibration table for OB1 is always 1000

#MFS constants
H20_CALIBRATION = 0
IPA_CALIBRATION = 1 # can create a class for these? meh
MFS_SENSOR_TYPE = 5
MFS_DEFAULT_RESOLUTION = 7 # [0..7] => [9..16] bits

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
    MULTIPLE_CONNECTIONS                   = 8007
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
    ErrorCode.NO_PRESSURE_SENSOR_OB1_MK3:           "No pressure sensor compatible with OB1",
    ErrorCode.NO_DIGITAL_PRESSURE_SENSOR_MK3_PLUS:  "No Digital pressure sensor compatible with OB1",
    ErrorCode.NO_DIGITAL_FLOW_SENSOR_MK3:           "No Digital Flow sensor compatible with OB1",
    ErrorCode.NO_IPA_CONFIG_FOR_SENSOR:             "No IPA config for this sensor",
    ErrorCode.SENSOR_NOT_COMPATIBLE:                "Sensor not compatible with AF1",
    ErrorCode.NO_INSTRUMENT_WITH_SELECTED_ID:       "No Instrument with selected ID",
    ErrorCode.MULTIPLE_CONNECTIONS:                 "ESI software might be connected to the device, close ESI before runnin this script",
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
    
   
class OB1:
    """
    OB1: a high-level, object‑oriented wrapper around the Elveflow OB1 SDK.    
    
    Parameters
    ----------
    device_name : str                       Instrument name from NI‑MAX (e.g. '113433').
    regulators : tuple[int, int, int, int]  Regulator installed (4, 4, 4, 4) for us
    dll_path : str                             
    sdk_path : str                          Root path that contains SDK and DLL folders like DLL32/, DLL64/, Python_32/, Python_64/.
    """
    
    def __init__(
        self,
        device_name: str,
        regulators = (REGULATOR_TYPE,)*4,
        dll_path: str | None = None,
        sdk_path: str | None = None,
        ) -> None:
        
        if not isinstance(device_name, str) or not device_name:
            raise TypeError("device_name must be a non‑empty string")
        
        regs = tuple(int(x) for x in regulators)
        if len(regs) != 4:
            raise ValueError("regulators must be 4 integers (one per channel)")
        if any(x < 0 or x > 5 for x in regs):
            raise ValueError("regulator codes must be between 0 and 5 based on the pressure range of the channel")


        self.device_name = device_name
        self.regulators = regs
        self._instr_id = c_int32(-1)
        self._connected = False

        # --- Paths ---
        self._dll_path = dll_path
        self._sdk_path = sdk_path

        if self._dll_path is None or self._sdk_path is None:
            raise ValueError("Both dll_path and sdk_path must be provided")

        if not os.path.isdir(self._dll_path):
            raise FileNotFoundError(f"SDK DLL directory not found: {self._dll_path}")
        if not os.path.isdir(self._sdk_path):
            raise FileNotFoundError(f"SDK Python directory not found: {self._sdk_path}")
 
            
    def connectOB1(self) -> int:
    
        """
            Try to connect to OB1 
            Returns the Instrument ID if successful, -1 if connection fails.
        """
        
        if self._connected:
            return self._instr_id.value  # already connected, return existing ID

        regulators = self.regulators
        instrument_ID = c_int32()
        
        error = OB1_Initialization(self.device_name.encode('ascii'), regulators[0], regulators[1], regulators[2], regulators[3], byref(instrument_ID)) 
    
        if error != 0:  # nonzero means error, return the specific code
                return error
        
        #print(f"initializeOB1 -> error: {error}, OB1 ID: {Instr_ID.value}")
        #_raise_if_error(error, "OB1_Initialization")

        # Success
        self._instr_id = instrument_ID
        self._connected = True
        
        return self._instr_id.value
    
    def closeOB1(self) -> int:
        if not self._connected:
            return
        error = self._sdk.OB1_Destructor(self._instr_id.value)
        self._check(error, "OB1_Destructor")
        self._instr_id = c_int32(-1)
        self._connected = False
        
        return error
    
    def addSensor(self, channel: int, calibration: int=IPA_CALIBRATION, resolution: int=MFS_RESOLUTION) -> int:     
        self._require_connection()
        error = self._sdk.OB1_Add_Sens(self._instr_id, channel, MFS_SENSOR_TYPE, 1, int(calibration), int(resolution), 0)
        #For digital sensors, the sensor type is automatically detected during this function call.
        self._check(error, "OB1_Add_Sens")
        return error
    

    def _require_connection(self) -> None:
        if not self._connected or self._instr_id.value < 0:
            raise RuntimeError("OB1 not connected. Call connect() first.")
    
    @staticmethod
    def _check(code: int, where: str) -> None:
        if isinstance(code, int) and code != 0:
            try:
                msg = ERROR_MESSAGES[ErrorCode(code)]
            except Exception:
                msg = f"Unrecognized error code {code}"
            raise RuntimeError(f"{where}: {msg} (code {code})")


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
