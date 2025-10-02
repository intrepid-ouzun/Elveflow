import sys
import time
import os
import threading
import queue

from ctypes import *
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/DLL64')#add the path to Elveflow64.lib here
sys.path.append('C:/Users/oykuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/Python/Python_64')#add the path of the Elveflow64.py

from Elveflow64 import *


def create_timestamped_path(original_path, timestamp_format="%Y%m%d"):
    """Efficiently create a timestamped file path from an original path."""
    path_obj = Path(original_path)
    timestamp = time.strftime(timestamp_format)
    return str(path_obj.parent / f"{path_obj.stem}_{timestamp}{path_obj.suffix}")

def calibrate_new(instr_id, base_path, verbose=True):
    """
    Perform new calibration and save to timestamped path.
    
    Args:
        instr_id: OB1 instrument ID
        base_path: Base path for calibration file (e.g., "C:/Users/oykuz/calibration.calib")
        verbose: Print detailed progress information
    
    Returns:
        tuple: (success: bool, saved_path: str, error_code: int)
    """
    if verbose:
        print(f"\n=== NEW CALIBRATION ===")
        print(f"Base path: {base_path}")
        print("-" * 30)
    
    try:
        # Create timestamped path
        timestamped_path = create_timestamped_path(base_path)
        if verbose:
            print(f"Calibration will be saved to: {timestamped_path}")
        
        # Perform calibration
        if verbose:
            print("Starting calibration process...")
        
        start_time = time.time()
        error = OB1_Calib(instr_id)
        calibration_time = time.time() - start_time
        
        if error != 0:
            if verbose:
                print(f"Calibration failed with error code: {error}")
            return False, "", error
        
        if verbose:
            print(f"Calibration completed in {calibration_time:.1f} seconds")
        
        # Save calibration to timestamped path
        path_buf = create_string_buffer(timestamped_path.encode('ascii'))
        error = OB1_Calib_Save(instr_id, path_buf)
        
        if error != 0:
            if verbose:
                print(f"Failed to save calibration with error code: {error}")
            return False, "", error
        
        if verbose:
            print(f"Calibration saved successfully to: {timestamped_path}")
        
        # Load the newly created calibration
        error = OB1_Calib_Load(instr_id, path_buf)
        
        if error != 0:
            if verbose:
                print(f"Warning: Failed to load saved calibration with error code: {error}")
            return True, timestamped_path, error  # Still return success for saving
        
        if verbose:
            print("Calibration loaded successfully")
            print("=" * 30)
        
        return True, timestamped_path, 0
    
    except Exception as e:
        if verbose:
            print(f"Exception during calibration: {e}")
        return False, "", -1

def existing_calibration(instr_id, calib_path, verbose=True):
    """
    Load existing calibration from specified path.
    
    Args:
        instr_id: OB1 instrument ID
        calib_path: Path to existing calibration file
        verbose: Print detailed progress information
    
    Returns:
        tuple: (success: bool, error_code: int)
    """
    if verbose:
        print(f"\n=== LOAD EXISTING CALIBRATION ===")
        print(f"Calibration path: {calib_path}")
        print("-" * 30)
    
    try:
        # Check if file exists
        if not os.path.exists(calib_path):
            if verbose:
                print(f"Error: Calibration file not found at {calib_path}")
            return False, -1
        
        if verbose:
            print("Loading existing calibration...")
        
        # Load calibration
        path_buf = create_string_buffer(calib_path.encode('ascii'))
        error = OB1_Calib_Load(instr_id, path_buf)
        
        if error != 0:
            if verbose:
                print(f"Failed to load calibration with error code: {error}")
            return False, error
        
        if verbose:
            print("Calibration loaded successfully")
            print("=" * 30)
        
        return True, 0
    
    except Exception as e:
        if verbose:
            print(f"Exception during calibration load: {e}")
        return False, -1

def ramp_pressure(instr_id, channel, pressure_mbar, ramp_time=0.0, 
                 sample_dt=0.1, verbose=True):
    """
    Ramp up pressure on a channel to a target value.
    
    Args:
        instr_id: OB1 instrument ID
        channel: Channel to control
        pressure_mbar: Target pressure to set in mbar
        ramp_time: Time to ramp up pressure in seconds (0 = immediate, default: 0.0)
        sample_dt: Sampling interval in seconds (default: 0.1)
        verbose: Print detailed progress information
    
    Returns:
        dict: Pressure ramp results including statistics
    """
    if verbose:
        print(f"\n=== RAMP PRESSURE ===")
        print(f"Channel: {channel.value}")
        print(f"Target Pressure: {pressure_mbar} mbar")
        print(f"Ramp Time: {ramp_time} seconds")
        print(f"Sampling interval: {sample_dt} seconds")
        print("-" * 40)
    
    # Initialize data logging
    time_log = []
    pressure_log = []
    flow_log = []
    target_pressure_log = []
    
    start_time = time.time()
    
    try:
        if ramp_time > 0:
            # Gradual pressure ramp-up
            if verbose:
                print(f"Ramping pressure from 0 to {pressure_mbar} mbar over {ramp_time} seconds...")
            
            ramp_start = time.time()
            ramp_steps = int(ramp_time / sample_dt)
            
            for step in range(ramp_steps + 1):
                current_time = time.time()
                elapsed_ramp = current_time - ramp_start
                
                # Calculate current target pressure (linear ramp)
                ramp_progress = min(elapsed_ramp / ramp_time, 1.0)
                current_target_pressure = pressure_mbar * ramp_progress
                
                # Set current pressure
                error = OB1_Set_Press(instr_id, channel, c_double(current_target_pressure))
                if error != 0:
                    if verbose:
                        print(f"Error setting pressure during ramp: {error}")
                    return None
                
                # Read current pressure and flow
                sen = c_double()
                reg = c_double()
                error = OB1_Get_Data(instr_id, channel, byref(reg), byref(sen))
                
                if error == 0:
                    current_pressure = reg.value  # mbar
                    current_flow = sen.value  # µL/min
                    
                    # Log data
                    time_log.append(elapsed_ramp)
                    pressure_log.append(current_pressure)
                    flow_log.append(current_flow)
                    target_pressure_log.append(current_target_pressure)
                    
                    # Print ramp progress every 0.5 seconds
                    if verbose and int(elapsed_ramp * 2) % 1 == 0 and elapsed_ramp > 0:
                        ramp_progress_percent = ramp_progress * 100
                        print(f"Ramp Progress: {ramp_progress_percent:.1f}% - "
                              f"Target: {current_target_pressure:.1f} mbar - "
                              f"Actual: {current_pressure:.1f} mbar - "
                              f"Flow: {current_flow:.1f} µL/min")
                
                time.sleep(sample_dt)
            
            if verbose:
                print(f"Ramp completed. Target pressure {pressure_mbar} mbar reached.")
        else:
            # Immediate pressure setting
            if verbose:
                print("Setting pressure immediately...")
            
            error = OB1_Set_Press(instr_id, channel, c_double(pressure_mbar))
            if error != 0:
                if verbose:
                    print(f"Error setting pressure: {error}")
                return None
            
            if verbose:
                print(f"Pressure set to {pressure_mbar} mbar.")
    
    except KeyboardInterrupt:
        if verbose:
            print("\nPressure ramp interrupted by user")
        return None
    
    # Calculate final statistics
    actual_duration = time.time() - start_time
    avg_pressure = sum(pressure_log) / len(pressure_log) if pressure_log else 0
    min_pressure = min(pressure_log) if pressure_log else 0
    max_pressure = max(pressure_log) if pressure_log else 0
    avg_flow = sum(flow_log) / len(flow_log) if flow_log else 0
    min_flow = min(flow_log) if flow_log else 0
    max_flow = max(flow_log) if flow_log else 0
    
    # Calculate pressure stability (coefficient of variation)
    if len(pressure_log) > 1:
        pressure_variance = sum((x - avg_pressure) ** 2 for x in pressure_log) / len(pressure_log)
        pressure_std = pressure_variance ** 0.5
        pressure_stability = (pressure_std / avg_pressure) * 100 if avg_pressure > 0 else 0
    else:
        pressure_stability = 0
    
    # Prepare results
    results = {
        'target_pressure': pressure_mbar,
        'ramp_time': ramp_time,
        'actual_duration': actual_duration,
        'avg_pressure': avg_pressure,
        'min_pressure': min_pressure,
        'max_pressure': max_pressure,
        'avg_flow': avg_flow,
        'min_flow': min_flow,
        'max_flow': max_flow,
        'pressure_stability': pressure_stability,
        'time_log': time_log,
        'pressure_log': pressure_log,
        'flow_log': flow_log,
        'target_pressure_log': target_pressure_log
    }
    
    if verbose:
        print(f"\n=== PRESSURE RAMP RESULTS ===")
        print(f"Target Pressure: {pressure_mbar:.1f} mbar")
        print(f"Ramp Time: {ramp_time:.1f} seconds")
        print(f"Actual Duration: {actual_duration:.2f} seconds")
        print(f"Average Pressure: {avg_pressure:.1f} mbar")
        print(f"Pressure Range: {min_pressure:.1f} - {max_pressure:.1f} mbar")
        print(f"Average Flow: {avg_flow:.1f} µL/min")
        print(f"Flow Range: {min_flow:.1f} - {max_flow:.1f} µL/min")
        print(f"Pressure Stability: {pressure_stability:.2f}% CV")
        print("=" * 40)
    
    return results





def cleanup_MUX_DRI(MUX_DRI_Instr_Id, verbose=True):
    """
    Cleanup and close MUX DRI instrument.
    
    Args:
        MUX_DRI_Instr_Id: MUX DRI instrument ID
        verbose: Print progress information
    
    Returns:
        bool: Success status
    """
    if verbose:
        print(f"\n=== CLEANUP MUX DRI ===")
        print(f"MUX Instrument ID: {MUX_DRI_Instr_Id.value}")
        print("-" * 25)
    
    try:
        # Destruct MUX DRI
        if verbose:
            print("Destructing MUX DRI...")
        
        error = MUX_DRI_Destructor(MUX_DRI_Instr_Id.value)
        if error != 0:
            if verbose:
                print(f"Error destructing MUX DRI: {error}")
            return False
        
        if verbose:
            print("✓ MUX DRI cleaned up successfully")
            print("=" * 25)
        
        return True
    
    except Exception as e:
        if verbose:
            print(f"Exception during MUX DRI cleanup: {e}")
        return False

def closeOB1(instr_id, verbose=True):
    """
    Close OB1 instrument by setting all channels to zero pressure and destructing.
    
    Args:
        instr_id: OB1 instrument ID
        verbose: Print progress information
    
    Returns:
        int: Error code (0 = success)
    """
    if verbose:
        print(f"\n=== CLOSING OB1 ===")
        print(f"Instrument ID: {instr_id.value}")
        print("-" * 20)
    
    try:
        # Set all channels to zero pressure
        if verbose:
            print("Setting all channels to zero pressure...")
        
        stop_all_channels(instr_id, verbose=False)
        
        # Destruct the instrument
        if verbose:
            print("Destructing OB1 instrument...")
        
        error = OB1_Destructor(instr_id)
        if error != 0:
            if verbose:
                print(f"Error destructing OB1: {error}")
            return error
        
        if verbose:
            print("OB1 instrument closed successfully")
            print("=" * 20)
        
        return 0
    
    except Exception as e:
        if verbose:
            print(f"Exception during OB1 closure: {e}")
        return -1


def stop_all_channels(instr_id, verbose=True):
    """
    Stop all channels by setting pressure to zero for all regulators.
    
    Args:
        instr_id: OB1 instrument ID
        verbose: Print progress information
    
    Returns:
        int: Error code (0 = success)
    """
    if verbose:
        print(f"\n=== STOPPING ALL CHANNELS ===")
        print(f"Instrument ID: {instr_id.value}")
        print("-" * 30)
    
    try:
        error_count = 0
        
        # Stop all channels
        for channel_num in range(1, 5):  # Assuming 4 channels
            channel = c_int32(channel_num)
            
            
            # Set pressure to zero
            error = OB1_Set_Press(instr_id, channel, c_double(0))
            if error != 0:
                if verbose:
                    print(f"Error stopping channel {channel_num}: {error}")
                error_count += 1
        
        if verbose:
            if error_count == 0:
                print("All channels stopped successfully")
            else:
                print(f"Stopped channels with {error_count} errors")
            print("=" * 30)
        
        return 0 if error_count == 0 else -1
    
    except Exception as e:
        if verbose:
            print(f"Exception during channel stop: {e}")
        return -1

def home_MUX_DRI(MUX_DRI_Instr_Id, verbose=True):
    """
    Home the MUX distribution valve which is necessary before a session.
    
    Args:
        MUX_DRI_Instr_Id: MUX DRI instrument ID
        verbose: Print progress information
    
    Returns:
        tuple: (success: bool, answer_buffer: str, error_code: int)
    """
    if verbose:
        print(f"\n=== HOMING MUX DISTRIBUTION VALVE ===")
        print(f"MUX Instrument ID: {MUX_DRI_Instr_Id.value}")
        print("-" * 35)
    
    try:
        # Create answer buffer
        Answer = (c_char * 40)()
        
        if verbose:
            print("Sending homing command...")
        
        # Send homing command (0 = homing)
        error = MUX_DRI_Send_Command(MUX_DRI_Instr_Id.value, 0, Answer, 40)
        time.sleep(5.0)

        if error != 0:
            if verbose:
                print(f"Error during MUX homing: {error}")
            return False, "", error
        
        # Get the answer from the buffer
        answer_str = Answer.value.decode('ascii').strip()
        
        if verbose:
            print(f"Homing command sent successfully")
            print(f"Answer: {answer_str}")
            print("MUX distribution valve homed")
            print("=" * 35)
        
        return True, answer_str, 0
    
    except Exception as e:
        if verbose:
            print(f"Exception during MUX homing: {e}")
        return False, "", -1

def set_MUX_DRI_valve(MUX_DRI_Instr_Id, valve_position, rotation=0, verbose=True):
    """
    Set the MUX DRI valve to a specific position.
    
    Args:
        MUX_DRI_Instr_Id: MUX DRI instrument ID
        valve_position: Valve position to set (1, 2, 3, etc.)
        rotation: Rotation type (0=shortest, 1=clockwise, 2=counterclockwise, default: 0)
        verbose: Print progress information
    
    Returns:
        tuple: (success: bool, error_code: int)
    """
    if verbose:
        print(f"\n=== SET MUX DRI VALVE ===")
        print(f"MUX Instrument ID: {MUX_DRI_Instr_Id.value}")
        print(f"Valve Position to be set: {valve_position}")
        print(f"Rotation: {rotation} ({'shortest' if rotation == 0 else 'clockwise' if rotation == 1 else 'counterclockwise'})")
        print("-" * 25)
    
    try:
        if verbose:
            print(f"Setting valve to position {valve_position}...")
        
        # Set the valve position
        error = MUX_DRI_Set_Valve(MUX_DRI_Instr_Id.value, valve_position, rotation)
        time.sleep(3.0)

        if error != 0:
            if verbose:
                print(f"Error setting valve position: {error}")
            return False, error
        
        if verbose:
            # Verify the valve position was set correctly
            print("Verifying valve position...")
            success_verify, current_position, error_verify = get_MUX_DRI_valve(MUX_DRI_Instr_Id, verbose=False)
            
            if success_verify and current_position == valve_position:
                print(f"✓ Valve successfully set to position {valve_position} (verified)")
            elif success_verify:
                print(f"⚠ Warning: Valve position mismatch - Expected: {valve_position}, Actual: {current_position}")
            else:
                print(f"⚠ Warning: Could not verify valve position (error: {error_verify})")
            
            print(f"Valve set to position {valve_position} successfully")
            print("=" * 25)
        
        return True, 0
    
    except Exception as e:
        if verbose:
            print(f"Exception during valve setting: {e}")
        return False, -1

def get_MUX_DRI_valve(MUX_DRI_Instr_Id, verbose=True):
    """
    Get the current MUX DRI valve position.
    
    Args:
        MUX_DRI_Instr_Id: MUX DRI instrument ID
        verbose: Print progress information
    
    Returns:
        tuple: (success: bool, valve_position: int, error_code: int)
    """
    if verbose:
        print(f"\n=== GET MUX DRI VALVE POSITION ===")
        print(f"MUX Instrument ID: {MUX_DRI_Instr_Id.value}")
        print("-" * 30)
    
    try:
        if verbose:
            print("Reading current valve position...")
        
        # Get the current valve position
        valve = c_int32(-1)
        error = MUX_DRI_Get_Valve(MUX_DRI_Instr_Id.value, byref(valve))
        
        if error != 0:
            if verbose:
                print(f"Error reading valve position: {error}")
            return False, -1, error
        
        current_position = valve.value
        
        if verbose:
            print(f"Current valve position: {current_position}")
            print("=" * 30)
        
        return True, current_position, 0
    
    except Exception as e:
        if verbose:
            print(f"Exception during valve reading: {e}")
        return False, -1, -1

def read_channel_data(instr_id, channel, verbose=True):
    """
    Read pressure and flow rate from a channel with MFS sensor.
    
    Args:
        instr_id: OB1 instrument ID
        channel: Channel to read from
        verbose: Print the readings
    
    Returns:
        tuple: (success: bool, pressure_mbar: float, flow_ul_min: float, error_code: int)
    """
    try:
        # Read sensor data
        sen = c_double()  # Flow rate sensor
        reg = c_double()  # Pressure regulator
        error = OB1_Get_Data(instr_id, channel, byref(reg), byref(sen))
        
        if error != 0:
            if verbose:
                print(f"Error reading channel {channel.value} data: {error}")
            return False, 0.0, 0.0, error
        
        pressure = reg.value  # mbar
        flow_rate = sen.value  # µL/min
        
        if verbose:
            print(f"Channel {channel.value} - Pressure: {pressure:.1f} mbar, Flow: {flow_rate:.1f} µL/min")
        
        return True, pressure, flow_rate, 0
    
    except Exception as e:
        if verbose:
            print(f"Exception reading channel data: {e}")
        return False, 0.0, 0.0, -1

def monitor_channel(instr_id, channel, duration_seconds=10.0, sample_dt=0.5, verbose=True):
    """
    Monitor pressure and flow rate for a specified duration.
    
    Args:
        instr_id: OB1 instrument ID
        channel: Channel to monitor
        duration_seconds: Duration to monitor in seconds
        sample_dt: Sampling interval in seconds
        verbose: Print progress information
    
    Returns:
        dict: Monitoring results with time series data
    """
    if verbose:
        print(f"\n=== MONITORING CHANNEL {channel.value} ===")
        print(f"Duration: {duration_seconds} seconds")
        print(f"Sampling interval: {sample_dt} seconds")
        print("-" * 35)
    
    # Initialize data logging
    time_log = []
    pressure_log = []
    flow_log = []
    
    start_time = time.time()
    
    try:
        while (time.time() - start_time) < duration_seconds:
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # Read current data
            success, pressure, flow_rate, error = read_channel_data(instr_id, channel, verbose=False)
            
            if success:
                # Log data
                time_log.append(elapsed_time)
                pressure_log.append(pressure)
                flow_log.append(flow_rate)
                
                # Print progress every 2 seconds
                if verbose and int(elapsed_time) % 2 == 0 and int(elapsed_time) > 0:
                    remaining = duration_seconds - elapsed_time
                    print(f"Time: {elapsed_time:.1f}s - Pressure: {pressure:.1f} mbar - Flow: {flow_rate:.1f} µL/min - Remaining: {remaining:.1f}s")
            else:
                if verbose:
                    print(f"Error reading data at {elapsed_time:.1f}s: {error}")
                break
            
            time.sleep(sample_dt)
    
    except KeyboardInterrupt:
        if verbose:
            print("\nMonitoring interrupted by user")
        return None
    
    # Calculate statistics
    if pressure_log and flow_log:
        avg_pressure = sum(pressure_log) / len(pressure_log)
        avg_flow = sum(flow_log) / len(flow_log)
        min_pressure = min(pressure_log)
        max_pressure = max(pressure_log)
        min_flow = min(flow_log)
        max_flow = max(flow_log)
        
        # Calculate stability (coefficient of variation)
        pressure_variance = sum((x - avg_pressure) ** 2 for x in pressure_log) / len(pressure_log)
        pressure_std = pressure_variance ** 0.5
        pressure_stability = (pressure_std / avg_pressure) * 100 if avg_pressure > 0 else 0
        
        flow_variance = sum((x - avg_flow) ** 2 for x in flow_log) / len(flow_log)
        flow_std = flow_variance ** 0.5
        flow_stability = (flow_std / avg_flow) * 100 if avg_flow > 0 else 0
        
        results = {
            'channel': channel.value,
            'duration': duration_seconds,
            'samples': len(pressure_log),
            'avg_pressure': avg_pressure,
            'min_pressure': min_pressure,
            'max_pressure': max_pressure,
            'pressure_stability': pressure_stability,
            'avg_flow': avg_flow,
            'min_flow': min_flow,
            'max_flow': max_flow,
            'flow_stability': flow_stability,
            'time_log': time_log,
            'pressure_log': pressure_log,
            'flow_log': flow_log
        }
        
        if verbose:
            print(f"\n=== MONITORING RESULTS ===")
            print(f"Channel: {channel.value}")
            print(f"Duration: {duration_seconds:.1f} seconds")
            print(f"Samples: {len(pressure_log)}")
            print(f"Average Pressure: {avg_pressure:.1f} mbar")
            print(f"Pressure Range: {min_pressure:.1f} - {max_pressure:.1f} mbar")
            print(f"Pressure Stability: {pressure_stability:.2f}% CV")
            print(f"Average Flow: {avg_flow:.1f} µL/min")
            print(f"Flow Range: {min_flow:.1f} - {max_flow:.1f} µL/min")
            print(f"Flow Stability: {flow_stability:.2f}% CV")
            print("=" * 35)
        
        return results
    
    return None

def log_channel_data_to_file(results, filename=None):
    """
    Log channel monitoring data to a CSV file.
    
    Args:
        results: Results dictionary from monitor_channel
        filename: Output filename (optional, will generate timestamped name if not provided)
    
    Returns:
        str: Filename of the saved file
    """
    if not results:
        print("No data to log")
        return ""
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"channel_monitoring_{results['channel']}_{timestamp}.csv"
    
    try:
        with open(filename, 'w') as f:
            f.write("Time_s,Pressure_mbar,Flow_ul_min\n")
            for i in range(len(results['time_log'])):
                f.write(f"{results['time_log'][i]:.2f},{results['pressure_log'][i]:.2f},{results['flow_log'][i]:.2f}\n")
        
        print(f"Data logged to: {filename}")
        return filename
    
    except Exception as e:
        print(f"Error logging data: {e}")
        return ""

def plot_channel_data(results, save_plot=True, show_plot=True, filename=None):
    """
    Create plot for pressure data only.
    
    Args:
        results: Results dictionary from monitor_channel
        save_plot: Save plot to file (default: True)
        show_plot: Display plot (default: True)
        filename: Output filename (optional, will generate timestamped name if not provided)
    
    Returns:
        str: Filename of the saved plot
    """
    if not results or not results.get('time_log'):
        print("No data to plot")
        return ""
    
    # Set up the plot style
    plt.style.use('default')
    fig, ax = plt.subplots(1, 1, figsize=(12, 6))
    fig.suptitle(f'Channel {results["channel"]} - Pressure Monitoring', 
                 fontsize=16, fontweight='bold')
    
    # Use time in seconds directly
    time_seconds = results['time_log']
    
    # Plot: Pressure
    ax.plot(time_seconds, results['pressure_log'], 'b-', linewidth=2, label='Pressure')
    ax.axhline(y=results['avg_pressure'], color='r', linestyle='--', alpha=0.7, 
                label=f'Average: {results["avg_pressure"]:.1f} mbar')
    ax.fill_between(time_seconds, results['pressure_log'], alpha=0.3, color='blue')
    ax.set_xlabel('Time (seconds)', fontsize=12, fontweight='bold')
    ax.set_ylabel('Pressure (mbar)', fontsize=12, fontweight='bold')
    ax.set_title('Pressure vs Time', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.legend()
    
    # Add pressure statistics text
    pressure_text = f'Range: {results["min_pressure"]:.1f} - {results["max_pressure"]:.1f} mbar\n'
    pressure_text += f'Stability: {results["pressure_stability"]:.2f}% CV'
    ax.text(0.02, 0.98, pressure_text, transform=ax.transAxes, 
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    
    # Add overall statistics
    stats_text = f'Duration: {results["duration"]:.1f} seconds\n'
    stats_text += f'Samples: {results["samples"]}\n'
    stats_text += f'Channel: {results["channel"]}'
    fig.text(0.98, 0.02, stats_text, transform=fig.transFigure, 
             verticalalignment='bottom', horizontalalignment='right',
             bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8))
    
    plt.tight_layout()
    
    # Save plot if requested
    if save_plot:
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"channel_plot_{results['channel']}_{timestamp}.png"
        
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"Plot saved to: {filename}")
    
    # Show plot if requested
    if show_plot:
        plt.show()
    else:
        plt.close()
    
    return filename

def plot_realtime_monitoring(instr_id, channel, duration_seconds=30.0, sample_dt=0.5, 
                           update_interval=2.0, save_plot=True, verbose=True):
    """
    Real-time monitoring with live plotting.
    
    Args:
        instr_id: OB1 instrument ID
        channel: Channel to monitor
        duration_seconds: Duration to monitor
        sample_dt: Sampling interval
        update_interval: Plot update interval in seconds
        save_plot: Save final plot
        verbose: Print progress information
    
    Returns:
        dict: Monitoring results
    """
    if verbose:
        print(f"\n=== REAL-TIME MONITORING WITH PLOTTING ===")
        print(f"Channel: {channel.value}")
        print(f"Duration: {duration_seconds} seconds")
        print(f"Sampling: {sample_dt}s, Plot updates: {update_interval}s")
        print("-" * 45)
    
    # Initialize data logging
    time_log = []
    pressure_log = []
    flow_log = []
    
    # Set up interactive plotting
    plt.ion()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))
    fig.suptitle(f'Real-time Monitoring - Channel {channel.value}', fontsize=16, fontweight='bold')
    
    start_time = time.time()
    last_plot_update = start_time
    
    try:
        while (time.time() - start_time) < duration_seconds:
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # Read current data
            success, pressure, flow_rate, error = read_channel_data(instr_id, channel, verbose=False)
            
            if success:
                # Log data
                time_log.append(elapsed_time)
                pressure_log.append(pressure)
                flow_log.append(flow_rate)
                
                # Update plot periodically
                if current_time - last_plot_update >= update_interval:
                    # Clear and redraw plots
                    ax1.clear()
                    ax2.clear()
                    
                    # Plot pressure
                    ax1.plot(time_log, pressure_log, 'b-', linewidth=2)
                    ax1.set_ylabel('Pressure (mbar)')
                    ax1.set_title('Pressure vs Time')
                    ax1.grid(True, alpha=0.3)
                    
                    # Plot flow rate
                    ax2.plot(time_log, flow_log, 'g-', linewidth=2)
                    ax2.set_xlabel('Time (s)')
                    ax2.set_ylabel('Flow Rate (µL/min)')
                    ax2.set_title('Flow Rate vs Time')
                    ax2.grid(True, alpha=0.3)
                    
                    plt.tight_layout()
                    plt.draw()
                    plt.pause(0.01)
                    
                    last_plot_update = current_time
                
                if verbose and int(elapsed_time) % 5 == 0 and int(elapsed_time) > 0:
                    remaining = duration_seconds - elapsed_time
                    print(f"Time: {elapsed_time:.1f}s - P: {pressure:.1f} mbar - F: {flow_rate:.1f} µL/min - Remaining: {remaining:.1f}s")
            else:
                if verbose:
                    print(f"Error reading data at {elapsed_time:.1f}s: {error}")
                break
            
            time.sleep(sample_dt)
    
    except KeyboardInterrupt:
        if verbose:
            print("\nReal-time monitoring interrupted by user")
        return None
    
    finally:
        plt.ioff()
    
    # Calculate final statistics
    if pressure_log and flow_log:
        avg_pressure = sum(pressure_log) / len(pressure_log)
        avg_flow = sum(flow_log) / len(flow_log)
        min_pressure = min(pressure_log)
        max_pressure = max(pressure_log)
        min_flow = min(flow_log)
        max_flow = max(flow_log)
        
        # Calculate stability
        pressure_variance = sum((x - avg_pressure) ** 2 for x in pressure_log) / len(pressure_log)
        pressure_std = pressure_variance ** 0.5
        pressure_stability = (pressure_std / avg_pressure) * 100 if avg_pressure > 0 else 0
        
        flow_variance = sum((x - avg_flow) ** 2 for x in flow_log) / len(flow_log)
        flow_std = flow_variance ** 0.5
        flow_stability = (flow_std / avg_flow) * 100 if avg_flow > 0 else 0
        
        results = {
            'channel': channel.value,
            'duration': duration_seconds,
            'samples': len(pressure_log),
            'avg_pressure': avg_pressure,
            'min_pressure': min_pressure,
            'max_pressure': max_pressure,
            'pressure_stability': pressure_stability,
            'avg_flow': avg_flow,
            'min_flow': min_flow,
            'max_flow': max_flow,
            'flow_stability': flow_stability,
            'time_log': time_log,
            'pressure_log': pressure_log,
            'flow_log': flow_log
        }
        
        # Create final plot
        if save_plot:
            plot_channel_data(results, save_plot=True, show_plot=True)
        
        if verbose:
            print(f"\n=== REAL-TIME MONITORING COMPLETE ===")
            print(f"Samples: {len(pressure_log)}")
            print(f"Average Pressure: {avg_pressure:.1f} mbar")
            print(f"Average Flow: {avg_flow:.1f} µL/min")
            print("=" * 45)
        
        return results
    
    return None

# Global variables for continuous logging
_logging_active = False
_logging_thread = None
_logging_data = {
    'time_log': [],
    'pressure_log': [],
    'flow_log': [],
    'channel': None,
    'start_time': None,
    'samples': 0
}
_logging_lock = threading.Lock()

def start_continuous_logging(instr_id, channel, sample_dt=1.0, verbose=True):
    """
    Start continuous logging of pressure and flow rate data.
    
    Args:
        instr_id: OB1 instrument ID
        channel: Channel to monitor
        sample_dt: Sampling interval in seconds (default: 1.0)
        verbose: Print logging status
    
    Returns:
        bool: True if logging started successfully
    """
    global _logging_active, _logging_thread, _logging_data
    
    if _logging_active:
        if verbose:
            print("Continuous logging is already active")
        return True
    
    if verbose:
        print(f"\n=== STARTING CONTINUOUS LOGGING ===")
        print(f"Channel: {channel.value}")
        print(f"Sampling interval: {sample_dt} seconds")
        print("-" * 35)
    
    # Initialize logging data
    with _logging_lock:
        _logging_data = {
            'time_log': [],
            'pressure_log': [],
            'flow_log': [],
            'channel': channel.value,
            'start_time': time.time(),
            'samples': 0
        }
    
    # Start logging thread
    _logging_active = True
    _logging_thread = threading.Thread(
        target=_continuous_logging_worker,
        args=(instr_id, channel, sample_dt, verbose),
        daemon=True
    )
    _logging_thread.start()
    
    if verbose:
        print("✓ Continuous logging started")
        print("=" * 35)
    
    return True

def stop_continuous_logging(verbose=True):
    """
    Stop continuous logging.
    
    Args:
        verbose: Print logging status
    
    Returns:
        dict: Final logging results
    """
    global _logging_active, _logging_thread, _logging_data
    
    if not _logging_active:
        if verbose:
            print("Continuous logging is not active")
        return None
    
    if verbose:
        print(f"\n=== STOPPING CONTINUOUS LOGGING ===")
        print("Waiting for logging thread to finish...")
    
    # Stop logging
    _logging_active = False
    
    # Wait for thread to finish
    if _logging_thread and _logging_thread.is_alive():
        _logging_thread.join(timeout=5.0)
    
    # Get final results
    with _logging_lock:
        if _logging_data['samples'] > 0:
            # Calculate statistics
            pressure_log = _logging_data['pressure_log']
            flow_log = _logging_data['flow_log']
            
            avg_pressure = sum(pressure_log) / len(pressure_log)
            avg_flow = sum(flow_log) / len(flow_log)
            min_pressure = min(pressure_log)
            max_pressure = max(pressure_log)
            min_flow = min(flow_log)
            max_flow = max(flow_log)
            
            # Calculate stability
            pressure_variance = sum((x - avg_pressure) ** 2 for x in pressure_log) / len(pressure_log)
            pressure_std = pressure_variance ** 0.5
            pressure_stability = (pressure_std / avg_pressure) * 100 if avg_pressure > 0 else 0
            
            flow_variance = sum((x - avg_flow) ** 2 for x in flow_log) / len(flow_log)
            flow_std = flow_variance ** 0.5
            flow_stability = (flow_std / avg_flow) * 100 if avg_flow > 0 else 0
            
            results = {
                'channel': _logging_data['channel'],
                'duration': time.time() - _logging_data['start_time'],
                'samples': _logging_data['samples'],
                'avg_pressure': avg_pressure,
                'min_pressure': min_pressure,
                'max_pressure': max_pressure,
                'pressure_stability': pressure_stability,
                'avg_flow': avg_flow,
                'min_flow': min_flow,
                'max_flow': max_flow,
                'flow_stability': flow_stability,
                'time_log': _logging_data['time_log'].copy(),
                'pressure_log': pressure_log.copy(),
                'flow_log': flow_log.copy()
            }
            
            if verbose:
                print(f"✓ Logging stopped")
                print(f"Samples collected: {results['samples']}")
                print(f"Duration: {results['duration']:.1f} seconds")
                print(f"Average Pressure: {results['avg_pressure']:.1f} mbar")
                print(f"Average Flow: {results['avg_flow']:.1f} µL/min")
                print("=" * 35)
            
            return results
        else:
            if verbose:
                print("No data was collected during logging")
            return None

def _continuous_logging_worker(instr_id, channel, sample_dt, verbose):
    """
    Background worker for continuous logging.
    """
    global _logging_active, _logging_data
    
    if verbose:
        print("Continuous logging worker started")
    
    consecutive_errors = 0
    max_consecutive_errors = 5
    
    while _logging_active:
        try:
            # Read current data
            success, pressure, flow_rate, error = read_channel_data(instr_id, channel, verbose=False)
            
            if success:
                consecutive_errors = 0  # Reset error counter on success
                current_time = time.time()
                elapsed_time = current_time - _logging_data['start_time']
                
                # Add data to logs
                with _logging_lock:
                    _logging_data['time_log'].append(elapsed_time)
                    _logging_data['pressure_log'].append(pressure)
                    _logging_data['flow_log'].append(flow_rate)
                    _logging_data['samples'] += 1
                
                # Print progress every 10 samples
                if verbose and _logging_data['samples'] % 10 == 0:
                    print(f"Logged {_logging_data['samples']} samples - "
                          f"P: {pressure:.1f} mbar, F: {flow_rate:.1f} µL/min")
            else:
                consecutive_errors += 1
                if verbose:
                    print(f"Error reading data (attempt {consecutive_errors}): {error}")
                
                # Stop logging if too many consecutive errors
                if consecutive_errors >= max_consecutive_errors:
                    if verbose:
                        print(f"Stopping logging due to {max_consecutive_errors} consecutive errors")
                    break
            
            time.sleep(sample_dt)
            
        except Exception as e:
            consecutive_errors += 1
            if verbose:
                print(f"Exception in logging worker (attempt {consecutive_errors}): {e}")
            
            if consecutive_errors >= max_consecutive_errors:
                if verbose:
                    print(f"Stopping logging due to {max_consecutive_errors} consecutive exceptions")
                break
            
            time.sleep(sample_dt)  # Wait before retrying
    
    if verbose:
        print(f"Continuous logging worker stopped (collected {_logging_data['samples']} samples)")

def get_logging_status():
    """
    Get current logging status.
    
    Returns:
        dict: Current logging status and statistics
    """
    global _logging_active, _logging_data
    
    with _logging_lock:
        if _logging_active:
            current_time = time.time()
            elapsed_time = current_time - _logging_data['start_time']
            
            return {
                'active': True,
                'channel': _logging_data['channel'],
                'samples': _logging_data['samples'],
                'elapsed_time': elapsed_time,
                'start_time': _logging_data['start_time']
            }
        else:
            return {
                'active': False,
                'channel': None,
                'samples': 0,
                'elapsed_time': 0,
                'start_time': None
            }

def save_continuous_logging_data(filename=None):
    """
    Save continuous logging data to CSV file.
    
    Args:
        filename: Output filename (optional)
    
    Returns:
        str: Filename of saved file
    """
    global _logging_data
    
    with _logging_lock:
        if not _logging_data['samples']:
            print("No data to save")
            return ""
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"continuous_logging_{_logging_data['channel']}_{timestamp}.csv"
        
        try:
            with open(filename, 'w') as f:
                f.write("Time_s,Pressure_mbar,Flow_ul_min\n")
                for i in range(len(_logging_data['time_log'])):
                    f.write(f"{_logging_data['time_log'][i]:.2f},"
                           f"{_logging_data['pressure_log'][i]:.2f},"
                           f"{_logging_data['flow_log'][i]:.2f}\n")
            
            print(f"Continuous logging data saved to: {filename}")
            return filename
        
        except Exception as e:
            print(f"Error saving continuous logging data: {e}")
            return ""

def main():
    """
    Pressure profile experiment with MUX DRI valve 1:
    1. Initialize OB1 and MUX DRI
    2. Home and set MUX DRI valve to position 1
    3. Load calibration
    4. Start continuous logging
    5. Apply pressure profile (priming + sampling pulses at 400 mbar)
    6. Save plot and cleanup
    """
    
    # Initialize OB1
    channel = c_int32(1)
    instr_id = c_int32(-1)
    
    print("=== INITIALIZING OB1 ===")
    error = OB1_Initialization('OB1'.encode('ascii'), 0, 0, 0, 0, byref(instr_id))
    if error != 0:
        print(f"Error initializing OB1: {error}")
        return
    print("✓ OB1 initialized successfully")
    
    # Initialize MUX DRI
    MUX_DRI_Instr_Id = c_int32(-1)
    print("\n=== INITIALIZING MUX DRI ===")
    error = MUX_DRI_Initialization('MUX_DRI'.encode('ascii'), 0, 0, 0, 0, byref(MUX_DRI_Instr_Id))
    if error != 0:
        print(f"Error initializing MUX DRI: {error}")
        return
    print("✓ MUX DRI initialized successfully")
    
    # Home MUX DRI valve
    print("\n=== HOMING MUX DRI VALVE ===")
    home_MUX_DRI(MUX_DRI_Instr_Id, verbose=True)
    
    # Set MUX DRI valve to position 1
    print("\n=== SETTING MUX DRI VALVE TO POSITION 1 ===")
    set_MUX_DRI_valve(MUX_DRI_Instr_Id, 1, verbose=True)
    
    try:
        # Load existing calibration
        print("\n=== LOADING EXISTING CALIBRATION ===")
        calibration_path = r"C:\Users\oykuz\calibration_20250929.calib"
        success = existing_calibration(
            instr_id.value, 
            calibration_path, 
            verbose=True
        )
        
        if not success:
            print(f"✗ Calibration loading failed")
            return
        
        print(f"✓ Calibration loaded successfully from: {calibration_path}")

        print("Setting pressure to zero...")
        error = OB1_Set_Press(instr_id.value, channel, c_double(0))
        
        # Start continuous logging
        print("\n=== STARTING CONTINUOUS LOGGING ===")
        start_continuous_logging(instr_id, channel, sample_dt=1.0, verbose=True)
        
        # Apply pressure profile: priming pulse + sampling pulse
        print("\n=== STARTING PRESSURE PROFILE EXPERIMENT ===")
        print("Applying pressure profile: priming pulse + sampling pulse")
        
        # Send pressure pulse to prime the line: 600 mbar with 5s ramp up, 3s hold, 5s ramp down
        print("\n=== PRIME THE LINE ===")
        print("Sending 600 mbar pressure pulse to prime the line...")
        print("Ramp up: 5s, Hold: 3s, Ramp down: 5s")
        
        pulse_start = time.time()
        ramp_up_time = 5.0     # 5 seconds ramp up
        hold_time = 3.0        # 3 seconds hold
        ramp_down_time = 5.0   # 5 seconds ramp down
        pulse_duration = ramp_up_time + hold_time + ramp_down_time  # 13 seconds total
        target_pressure = 600.0
        
        while (time.time() - pulse_start) < pulse_duration:
            elapsed_pulse = time.time() - pulse_start
            
            # Calculate target pressure based on phase
            if elapsed_pulse <= ramp_up_time:
                # Ramp up phase
                progress = elapsed_pulse / ramp_up_time
                current_target = target_pressure * progress
                phase = "Ramp Up"
            elif elapsed_pulse <= ramp_up_time + hold_time:
                # Hold phase
                current_target = target_pressure
                phase = "Hold"
            else:
                # Ramp down phase
                ramp_down_elapsed = elapsed_pulse - (ramp_up_time + hold_time)
                progress = ramp_down_elapsed / ramp_down_time
                current_target = target_pressure * (1.0 - progress)
                phase = "Ramp Down"
            
            # Set pressure
            error = OB1_Set_Press(instr_id, channel, c_double(current_target))
            
            # Read current pressure values
            reg = c_double()
            error_read = OB1_Get_Data(instr_id, channel, byref(reg), None)
            
            if error_read == 0:
                actual_pressure = reg.value
                
                print(f"Priming - {phase}: {elapsed_pulse:.1f}s/{pulse_duration:.1f}s - "
                      f"Target: {current_target:.1f} mbar - "
                      f"Actual: {actual_pressure:.1f} mbar")
            
            time.sleep(0.5)  # Update every 0.5 seconds
        
        # Ramp down pressure to 0 over 5 seconds after priming pulse
        print("Ramping down pressure to 0 over 5 seconds...")
        ramp_down_start = time.time()
        ramp_down_duration = 5.0
        initial_pressure = target_pressure
        
        while (time.time() - ramp_down_start) < ramp_down_duration:
            elapsed_ramp = time.time() - ramp_down_start
            progress = elapsed_ramp / ramp_down_duration
            current_target = initial_pressure * (1.0 - progress)
            
            # Set pressure
            error = OB1_Set_Press(instr_id, channel, c_double(current_target))
            
            # Read current pressure values
            reg = c_double()
            error_read = OB1_Get_Data(instr_id, channel, byref(reg), None)
            
            if error_read == 0:
                actual_pressure = reg.value
                print(f"Priming - Ramp Down: {elapsed_ramp:.1f}s/{ramp_down_duration:.1f}s - "
                      f"Target: {current_target:.1f} mbar - "
                      f"Actual: {actual_pressure:.1f} mbar")
            
            time.sleep(0.2)  # Update every 0.2 seconds
        
        # Ensure pressure is set to 0
        OB1_Set_Press(instr_id, channel, c_double(0))
        print("✓ Line priming completed")
        
        # Wait 5 seconds between pulses
        print("Waiting 5 seconds before sampling pulse...")
        time.sleep(5.0)
        
        # Send sampling pulse: 400 mbar with 5s ramp up, 60s hold, 5s ramp down
        print("\n=== SAMPLING PULSE ===")
        print("Sending 400 mbar sampling pulse...")
        print("Ramp up: 5s, Hold: 60s, Ramp down: 5s")
        
        pulse_start = time.time()
        ramp_up_time = 5.0     # 5 seconds ramp up
        hold_time = 60.0       # 60 seconds hold
        ramp_down_time = 5.0   # 5 seconds ramp down
        pulse_duration = ramp_up_time + hold_time + ramp_down_time  # 70 seconds total
        target_pressure = 400.0
        
        while (time.time() - pulse_start) < pulse_duration:
            elapsed_pulse = time.time() - pulse_start
            
            # Calculate target pressure based on phase
            if elapsed_pulse <= ramp_up_time:
                # Ramp up phase
                progress = elapsed_pulse / ramp_up_time
                current_target = target_pressure * progress
                phase = "Ramp Up"
            elif elapsed_pulse <= ramp_up_time + hold_time:
                # Hold phase
                current_target = target_pressure
                phase = "Hold"
            else:
                # Ramp down phase
                ramp_down_elapsed = elapsed_pulse - (ramp_up_time + hold_time)
                progress = ramp_down_elapsed / ramp_down_time
                current_target = target_pressure * (1.0 - progress)
                phase = "Ramp Down"
            
            # Set pressure
            error = OB1_Set_Press(instr_id, channel, c_double(current_target))
            
            # Read current pressure values
            reg = c_double()
            error_read = OB1_Get_Data(instr_id, channel, byref(reg), None)
            
            if error_read == 0:
                actual_pressure = reg.value
                
                print(f"Sampling - {phase}: {elapsed_pulse:.1f}s/{pulse_duration:.1f}s - "
                      f"Target: {current_target:.1f} mbar - "
                      f"Actual: {actual_pressure:.1f} mbar")
            
            time.sleep(0.5)  # Update every 0.5 seconds
        
        # Ramp down pressure to 0 over 5 seconds after sampling pulse
        print("Ramping down pressure to 0 over 5 seconds...")
        ramp_down_start = time.time()
        ramp_down_duration = 5.0
        initial_pressure = target_pressure
        
        while (time.time() - ramp_down_start) < ramp_down_duration:
            elapsed_ramp = time.time() - ramp_down_start
            progress = elapsed_ramp / ramp_down_duration
            current_target = initial_pressure * (1.0 - progress)
            
            # Set pressure
            error = OB1_Set_Press(instr_id, channel, c_double(current_target))
            
            # Read current pressure values
            reg = c_double()
            error_read = OB1_Get_Data(instr_id, channel, byref(reg), None)
            
            if error_read == 0:
                actual_pressure = reg.value
                print(f"Sampling - Ramp Down: {elapsed_ramp:.1f}s/{ramp_down_duration:.1f}s - "
                      f"Target: {current_target:.1f} mbar - "
                      f"Actual: {actual_pressure:.1f} mbar")
            
            time.sleep(0.2)  # Update every 0.2 seconds
        
        # Ensure pressure is set to 0
        OB1_Set_Press(instr_id, channel, c_double(0))
        print("✓ Sampling pulse completed")
        
        print("✓ Pressure profile experiment completed")
    
    finally:
        # Cleanup
        print("\n=== CLEANUP ===")
        
        # Stop continuous logging
        print("Stopping continuous logging...")
        results = stop_continuous_logging(verbose=True)
        
        if results:
            print(f"✓ Continuous logging collected {results.get('samples', 0)} samples")
            print(f"✓ Duration: {results.get('duration', 0):.1f} seconds")
            print(f"✓ Time range: {min(results.get('time_log', [0])):.1f}s to {max(results.get('time_log', [0])):.1f}s")
            
            # Save the continuous logging data
            filename = save_continuous_logging_data()
            if filename:
                print(f"✓ Continuous logging data saved to: {filename}")
            
            # Create final plot from continuous logging
            print("\n=== CREATING FINAL PLOT ===")
            plot_filename = plot_channel_data(results, save_plot=True, show_plot=True)
            if plot_filename:
                print(f"✓ Final plot saved to: {plot_filename}")
        else:
            print("✗ No continuous logging data available for plotting")
        
        # Cleanup MUX DRI
        print("Cleaning up MUX DRI...")
        cleanup_MUX_DRI(MUX_DRI_Instr_Id, verbose=True)
        
        # Set pressure to zero and destruct OB1
        print("Setting pressure to zero...")
        error = OB1_Set_Press(instr_id.value, channel, c_double(0))
        
        print("Destructing OB1...")
        error = OB1_Destructor(instr_id.value)
        
        print("✓ Cleanup completed")
        print("Program finished successfully")

if __name__ == "__main__":
    main()