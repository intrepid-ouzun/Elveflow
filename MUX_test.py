import sys
sys.path.append('C:/Users/David/Documents/ELVESYS/Python/SDK373debug/DLL32')#add the path of the library here
sys.path.append('C:/Users/David/Documents/ELVESYS/Python/SDK373debug')#add the path of the LoadElveflow.py

from ctypes import *

from array import array

from Elveflow32 import *

Instr_ID = c_int32(-1)

def initializeMUX(COMport: str)
    """
    Initialize the 12/1 MUX distribution valve and return its Instrument ID
    
    
    """