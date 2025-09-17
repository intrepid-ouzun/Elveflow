import sys
import time
import os

from ctypes import *
from pathlib import Path

sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/DLL64')#add the path to Elveflow64.lib here
sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/Python/Python_64')#add the path of the Elveflow64.py

from Elveflow64 import *

def create_timestamped_path(original_path, timestamp_format="%Y%m%d"):
    """Efficiently create a timestamped file path from an original path."""
    path_obj = Path(original_path)
    timestamp = time.strftime(timestamp_format)
    return str(path_obj.parent / f"{path_obj.stem}_{timestamp}{path_obj.suffix}")

def inject_volume(instr_id, channel, target_volume_ul, flow_rate_ul_min=50.0, sample_dt=0.1, timeout_s=300):
    """
    Inject a specific volume using PID control.
    
    Args:
        instr_id: OB1 instrument ID
        channel: Channel to control (channel_refill or channel_sample)
        target_volume_ul: Target volume to inject in microliters
        flow_rate_ul_min: Target flow rate in µL/min (default: 50)
        sample_dt: Sampling interval in seconds (default: 0.1)
        timeout_s: Maximum time to wait in seconds (default: 300)
    
    Returns:
        tuple: (success: bool, actual_volume: float, injection_time: float)
    """
    print(f"Starting volume injection: {target_volume_ul} µL at {flow_rate_ul_min} µL/min")
    
    # Set target flow rate
    error = OB1_Set_Sens(instr_id, channel, c_double(flow_rate_ul_min))
    if error != 0:
        print(f"Error setting flow rate: {error}")
        return False, 0.0, 0.0
    
    # Initialize tracking variables
    injected_volume = 0.0
    start_time = time.time()
    last_time = start_time
    
    # Data logging
    time_log = []
    flow_log = []
    volume_log = []
    
    try:
        while injected_volume < target_volume_ul:
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # Check timeout
            if elapsed_time > timeout_s:
                print(f"Timeout reached ({timeout_s}s). Injected {injected_volume:.2f} µL of {target_volume_ul} µL")
                break
            
            # Read current flow rate
            sen = c_double()
            reg = c_double()
            error = OB1_Get_Data(instr_id, channel, byref(reg), byref(sen))
            
            if error != 0:
                print(f"Error reading sensor data: {error}")
                break
            
            current_flow = sen.value  # µL/min
            
            # Calculate volume injected since last reading
            dt = current_time - last_time
            volume_increment = current_flow * (dt / 60.0)  # Convert min to sec
            injected_volume += volume_increment
            
            # Log data
            time_log.append(elapsed_time)
            flow_log.append(current_flow)
            volume_log.append(injected_volume)
            
            # Update last time
            last_time = current_time
            
            # Print progress every 10% or every 5 seconds
            progress = (injected_volume / target_volume_ul) * 100
            if int(progress) % 10 == 0 and int(elapsed_time) % 5 == 0:
                print(f"Progress: {progress:.1f}% - {injected_volume:.2f}/{target_volume_ul} µL")
            
            # Sleep for sampling interval
            time.sleep(sample_dt)
    
    except KeyboardInterrupt:
        print("Injection interrupted by user")
        return False, injected_volume, elapsed_time
    
    finally:
        # Stop flow by setting pressure to 0
        error = OB1_Set_Press(instr_id, channel, c_double(0))
        if error != 0:
            print(f"Error stopping flow: {error}")
    
    injection_time = time.time() - start_time
    success = injected_volume >= target_volume_ul * 0.95  # Consider 95% as success
    
    print(f"Injection complete: {injected_volume:.2f} µL in {injection_time:.1f}s")
    print(f"Average flow rate: {(injected_volume / injection_time * 60):.2f} µL/min")
    
    return success, injected_volume, injection_time

#MFS used to measure flow rate of the refill and sample lines
channel_refill = c_int32(1)
channel_sample = c_int32(2)

Instr_ID=c_int32(-1) # handle for the SDK communication, increments with each new instrument initialized
error = OB1_Initialization('113433'.encode('ascii'),0,0,0,0,byref(Instr_ID)) 
error = OB1_Add_Sens(Instr_ID.value, channel_refill.value, 5, 1, 1, 7, 0) 
error = OB1_Add_Sens(Instr_ID.value, channel_sample.value, 5, 1, 1, 7, 0) 


# ----- CALIBRATION -----
Calib_path = r"C:\Users\oykuz\calibration.calib"
# Efficient timestamping using helper function
new_path = create_timestamped_path(Calib_path)
path_buf = create_string_buffer(new_path.encode('ascii'))

start = time.time() # Start timer
error = OB1_Calib (Instr_ID.value)
elapsed = time.time() - start
print ("ran calibration in %d seconds with exit code %d" %(elapsed, error))
error = OB1_Calib_Save(Instr_ID.value, path_buf)
print("Saved calibration to %s with error code %d" % (new_path, error))

#reset pressures on both channels to start
error = OB1_Set_Press(Instr_ID.value, channel_refill, c_double(0)) 
error = OB1_Set_Press(Instr_ID.value, channel_sample, c_double(0)) 

# --- PID CONTROL SETUP ---
#add PI controllers to both refill and sample channels and start them
k_p = 0.001
k_i = 0.001
error = PID_Add_Remote(Instr_ID.value, channel_refill, Instr_ID.value, channel_refill, k_p, k_i, 1)
error = PID_Add_Remote(Instr_ID.value, channel_sample, Instr_ID.value, channel_sample, k_p, k_i, 1)
error = PID_Set_Running_Remote(Instr_ID.value, channel_refill, c_int32(1)) 
error = PID_Set_Running_Remote(Instr_ID.value, channel_sample, c_int32(1)) 

#adjust parameters if needed
# error = PID_Set_Params_Remote(Instr_ID.value, channel_refill, 1, k_p, k_i)
# error = PID_Set_Params_Remote(Instr_ID.value, channel_sample, 1, k_p, k_i)

# --- REFILL CONTROL START ---
error = OB1_Set_Sens(Instr_ID.value, channel_refill, c_double(0))

# Example usage of inject_volume function:
# Inject 100 µL through the refill channel at 50 µL/min
success, actual_volume, injection_time = inject_volume(
    Instr_ID.value, 
    channel_refill, 
    target_volume_ul=100.0, 
    flow_rate_ul_min=50.0
)

# Inject 50 µL through the sample channel at 25 µL/min
success, actual_volume, injection_time = inject_volume(
    Instr_ID.value, 
    channel_sample, 
    target_volume_ul=50.0, 
    flow_rate_ul_min=25.0
)


# --- LOOP TO CONTINIOUSLY SAMPLE AND REFILL WITH TIMESTAMPS ---


