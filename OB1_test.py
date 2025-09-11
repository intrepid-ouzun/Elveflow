import sys, os
from ctypes import byref, c_double, c_int32
from dataclasses import dataclass
from enum import IntEnum
import time

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
REGULATOR_TYPE = 0 #SET 0 FOR OB1 MK4!
CALIB_LEN = 1000 #length of the calibration table for OB1 is always 1000

#MFS constants
H20_CALIBRATION = 0
IPA_CALIBRATION = 1 # can create a class for these? meh
MFS_SENSOR_TYPE = 5
MFS_RESOLUTION = 7 # [0..7] => [9..16] bits

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


def loadElveflowModule(dll_dir: str, py_dir: str):
    """ 
    A helper function to load the DLL and Python SDK to path to be called during OB1 object initialization.

    Args:
        dll_dir (str): path to Elveflow64.lib in str format
        py_dir (str): path to Elveflow64.py in str format
        
        e.g. 
        dll_dir = 'C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/DLL64'
        py_dir = 'C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/Python/Python_64'

    """
    dll_dir = os.path.abspath(dll_dir)
    py_dir  = os.path.abspath(py_dir)

    if not os.path.isdir(dll_dir):
        raise FileNotFoundError(f"DLL directory not found: {dll_dir}")
    if not os.path.isdir(py_dir):
        raise FileNotFoundError(f"Python wrapper directory not found: {py_dir}")

    if py_dir not in sys.path:
        sys.path.append(py_dir)
        
    if dll_dir not in sys.path:
        sys.path.append(dll_dir)
        
    return 0

    
   
class OB1:
    """
    OB1: a high-level wrapper around the Elveflow OB1 SDK.    
    
    Parameters
    ----------
    device_name : str                       Instrument name from NI‑MAX (e.g. '113433').
    regulators : tuple[int, int, int, int]  Regulator codes are always (0, 0, 0, 0) for OB1 MK4 athough the regulator code is 4 for -900,1000 mbar
    dll_path : str                             
    sdk_path : str                          Root path that contains SDK and DLL folders like DLL32/, DLL64/, Python_32/, Python_64/.
    """
    
    __slots__ = (
        "device_name", "regulators", "_dll_path", "_sdk_path",
        "_lib", "_connected", "__Instr_Id"
    )
    
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
        self._connected = False
        self._instr_id = c_int32(-1)

        # --- Paths ---
        self._dll_path = dll_path
        self._sdk_path = sdk_path

        # load SDK module using the separate loader function
        error = loadElveflowModule(self._dll_path, self._sdk_path)
        
        error = OB1_Initialization(self.device_name.encode('ascii'),0,0,0,0,byref(self._instr_id)) 
        self._check(err, "OB1Initialization")

        self._connected = True

    
    def closeOB1(self) -> int:
        if not self._connected:
            return -1
        #error = self._sdk.OB1_Destructor(self._instr_id.value)
        error = OB1_Destructor(self._instr_id.value)
        self._check(error, "OB1_Destructor")
        self._instr_id = c_int32(-1)
        self._connected = False
        
        return self._instr_id.value
    
    def addSensor(self, channel: int, calibration: int=IPA_CALIBRATION, resolution: int=MFS_RESOLUTION) -> int:     
        self._require_connection()
        error = OB1_Add_Sens(self._instr_id.value, channel, MFS_SENSOR_TYPE, 1, int(calibration), int(resolution), 0)
        #For digital sensors, the sensor type is automatically detected during this function call.
        self._check(error, "OB1_Add_Sens")
        return self._instr_id.value
    
    def performCaibration(self, path: str):
    
        #error checking
        if not os.path.isdir(path):
            raise RuntimeError(f"Directory does not exist: {path}")
        # Directory must be writable
        if not os.access(path, os.W_OK):
            raise RuntimeError(f"Directory is not writable: {path}")
        if not os.path.isfile(path):
            raise RuntimeError(f"File does not exist: {path}")
        # Path must be ASCII encodable
        try:
            encoded = path.encode('ascii')
        except UnicodeEncodeError:
            raise RuntimeError("Path contains non-ASCII characters, not supported by OB1 SDK.")

        path_buf = create_string_buffer(path.encode('ascii'))  # char path[] (array), NUL added automatically

        start = time.time() # Start timer

        OB1_Calib (self._instr_id.value)
        error = OB1_Calib_Save(self._instr_id.value, path_buf)
        
        elapsed = time.time() - start
        print(f"Calibration completed in {elapsed:.2f} seconds")
        print(f'Calibration file saved at: {path}')
        #print(f'OB1_performCalibration -> error: {error}')
        _raise_if_error(error, "OB1: performCalibration")
        
    def loadCalibration(self, path: str):
        """
        Load a calibration file from the specified path.
        Input must be a raw string e.g. r"C:\Users\oykuz\calib.txt"
        """    
        #error checking
        if not os.path.isdir(path):
            raise RuntimeError(f"Directory does not exist: {path}")
        if not os.path.isfile(path):
            raise RuntimeError(f"File does not exist: {path}")
        # Path must be ASCII encodable
        try:
            encoded = path.encode('ascii')
        except UnicodeEncodeError:
            raise RuntimeError("Path contains non-ASCII characters, not supported by OB1 SDK.")

        path_buf = create_string_buffer(path.encode('ascii'))  # char path[] (array), NUL added automatically

        error = OB1_Calib_Load(self._instr_id.value, path_buf)
        #print(f"OB1_loadCalibration -> error: {error}").strip()
        self._check(error, "OB1: loadCalibration")
        
    
    def setPressure(self, channel: int, pressure: float = 0):
    
        if (pressure < -900 or pressure > 1000):
            print("Outside the pressure range of [-900,1000] mbar")
            return -1
        
        error = OB1_Set_Press(self._instr_id.value, c_int32(channel), c_double(pressure)) 
        #print(f"OB1_setPressure -> error: {error}").strip()
        self._check(error, "OB1: setPressure")

    def readMFS(instrID: int, channel: int):
        regulatorData = c_double()
        sensorData = c_double()
        
        error = OB1_Get_Data(instrID, channel, byref(regulatorData), byref(sensorData))
        if error != 0:
            raise RuntimeError(f"OB1_Get_Data error: {error}")
        return regulatorData.value, sensorData.value
    
    

    def _require_connection(self):
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

        





#PID feedbck function / depositing a certain volmume function
    
#keep adding working loop functions to test  
    
    
def main():
    
   #typical workflow would be initialize -> addSensor -> calibrate (perform, load) -> working loop -> closeOB
   deviceName = 'OB1_113433' 
   path = "C:/Users/oykuz/Calibration/Calib.txt" # path to save the calibration file to
   
   initializeOB1(deviceName)
   #addSensor(1) #if we want to add the MFS to ch1
   performCaibration(path)
   
   
   

if __name__ == "__main__":
    main()
