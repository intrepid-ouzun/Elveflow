import sys
import time
from datetime import datetime
from ctypes import *

sys.path.append('C:/Users/oykuuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/DLL64')
sys.path.append('C:/Users/oykuuz/ESI_V3_10_02/SDK_V3_10_01/SDK_V3_10_01/DLL/Python/Python_64')

from Elveflow64 import *

def run_flow_for_time(instr_id, channel, flow_rate_ul_min, duration_seconds, 
                     use_pid=True, k_p=0.001, k_i=0.001, verbose=True):
    """
    Run OB1 regulator at specified flow rate for a given duration.
    
    Args:
        instr_id: OB1 instrument ID
        channel: Channel to control
        flow_rate_ul_min: Target flow rate in µL/min
        duration_seconds: Duration to run in seconds
        use_pid: Whether to use PID control (default: True)
        k_p: Proportional gain for PID
        k_i: Integral gain for PID
        verbose: Print progress information
    
    Returns:
        dict: Flow run results
    """
    if verbose:
        print(f"\n=== FLOW RUN ===")
        print(f"Flow Rate: {flow_rate_ul_min} µL/min")
        print(f"Duration: {duration_seconds} seconds")
        print(f"Channel: {channel.value}")
        print(f"PID Control: {'Yes' if use_pid else 'No'}")
        print("-" * 30)
    
    # Initialize tracking
    start_time = time.time()
    total_volume = 0.0
    flow_readings = []
    pressure_readings = []
    
    try:
        if use_pid:
            # Set up PID control
            error = PID_Add_Remote(instr_id, channel, instr_id, channel, k_p, k_i, 1)
            if error != 0:
                print(f"Error setting up PID: {error}")
                return None
            
            error = PID_Set_Running_Remote(instr_id, channel, c_int32(1))
            if error != 0:
                print(f"Error starting PID: {error}")
                return None
            
            error = OB1_Set_Sens(instr_id, channel, c_double(flow_rate_ul_min))
            if error != 0:
                print(f"Error setting flow rate: {error}")
                return None
        else:
            # Direct pressure control
            pressure = flow_rate_ul_min * 2.0  # Rough conversion factor
            error = OB1_Set_Press(instr_id, channel, c_double(pressure))
            if error != 0:
                print(f"Error setting pressure: {error}")
                return None
        
        if verbose:
            print("Flow started. Monitoring...")
        
        # Main monitoring loop
        while (time.time() - start_time) < duration_seconds:
            # Read current flow rate and pressure
            sen = c_double()
            reg = c_double()
            error = OB1_Get_Data(instr_id, channel, byref(reg), byref(sen))
            
            if error == 0:
                current_flow = sen.value  # µL/min
                current_pressure = reg.value  # mbar
                
                # Calculate volume increment (assuming 0.1s sampling)
                volume_increment = current_flow * 0.1 / 60.0  # Convert to µL
                total_volume += volume_increment
                
                # Store readings
                flow_readings.append(current_flow)
                pressure_readings.append(current_pressure)
                
                # Print progress every 5 seconds
                elapsed = time.time() - start_time
                if verbose and int(elapsed) % 5 == 0 and int(elapsed) > 0:
                    remaining = duration_seconds - elapsed
                    progress = (elapsed / duration_seconds) * 100
                    print(f"Progress: {progress:.1f}% - {elapsed:.1f}s/{duration_seconds}s - "
                          f"Flow: {current_flow:.1f} µL/min - Volume: {total_volume:.2f} µL - "
                          f"Remaining: {remaining:.1f}s")
            
            time.sleep(0.1)  # 0.1 second sampling interval
    
    except KeyboardInterrupt:
        if verbose:
            print("\nFlow run interrupted by user")
        return None
    
    finally:
        # Stop flow
        if use_pid:
            error = PID_Set_Running_Remote(instr_id, channel, c_int32(0))
        
        error = OB1_Set_Press(instr_id, channel, c_double(0))
        if error != 0 and verbose:
            print(f"Error stopping flow: {error}")
    
    # Calculate final statistics
    actual_duration = time.time() - start_time
    avg_flow = sum(flow_readings) / len(flow_readings) if flow_readings else 0
    min_flow = min(flow_readings) if flow_readings else 0
    max_flow = max(flow_readings) if flow_readings else 0
    avg_pressure = sum(pressure_readings) / len(pressure_readings) if pressure_readings else 0
    
    # Calculate flow stability
    if len(flow_readings) > 1:
        flow_variance = sum((x - avg_flow) ** 2 for x in flow_readings) / len(flow_readings)
        flow_std = flow_variance ** 0.5
        flow_stability = (flow_std / avg_flow) * 100 if avg_flow > 0 else 0
    else:
        flow_stability = 0
    
    results = {
        'target_flow_rate': flow_rate_ul_min,
        'target_duration': duration_seconds,
        'actual_duration': actual_duration,
        'total_volume': total_volume,
        'avg_flow_rate': avg_flow,
        'min_flow_rate': min_flow,
        'max_flow_rate': max_flow,
        'avg_pressure': avg_pressure,
        'flow_stability': flow_stability,
        'flow_readings': flow_readings,
        'pressure_readings': pressure_readings
    }
    
    if verbose:
        print(f"\n=== RESULTS ===")
        print(f"Target Flow: {flow_rate_ul_min:.1f} µL/min")
        print(f"Actual Duration: {actual_duration:.2f} seconds")
        print(f"Total Volume: {total_volume:.2f} µL")
        print(f"Average Flow: {avg_flow:.1f} µL/min")
        print(f"Flow Range: {min_flow:.1f} - {max_flow:.1f} µL/min")
        print(f"Average Pressure: {avg_pressure:.1f} mbar")
        print(f"Flow Stability: {flow_stability:.2f}% CV")
        print("=" * 30)
    
    return results

def run_multiple_tests(instr_id, channel, test_configs, use_pid=True, verbose=True):
    """Run multiple flow tests with different configurations."""
    if verbose:
        print("MULTIPLE FLOW TESTS")
        print("=" * 25)
        print(f"Tests: {len(test_configs)}")
        print(f"Channel: {channel.value}")
        print("=" * 25)
    
    all_results = []
    
    for i, config in enumerate(test_configs, 1):
        flow_rate = config['flow_rate']
        duration = config['duration']
        
        if verbose:
            print(f"\n--- TEST {i}/{len(test_configs)} ---")
            print(f"Flow: {flow_rate} µL/min, Duration: {duration}s")
        
        result = run_flow_for_time(
            instr_id, channel, flow_rate, duration, 
            use_pid=use_pid, verbose=verbose
        )
        
        if result:
            result['test_number'] = i
            all_results.append(result)
            time.sleep(2.0)  # Brief pause between tests
        else:
            print(f"Test {i} failed")
    
    return all_results

def save_results(results, filename=None):
    """Save results to CSV file."""
    if not results:
        print("No results to save")
        return
    
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"flow_test_results_{timestamp}.csv"
    
    with open(filename, 'w') as f:
        f.write("Test_Number,Target_Flow_ul_min,Actual_Flow_ul_min,Target_Duration_s,Actual_Duration_s,"
               "Total_Volume_ul,Min_Flow_ul_min,Max_Flow_ul_min,Avg_Pressure_mbar,Flow_Stability_Percent\n")
        for result in results:
            test_num = result.get('test_number', 0)
            f.write(f"{test_num},{result['target_flow_rate']:.1f},{result['avg_flow_rate']:.1f},"
                   f"{result['target_duration']:.1f},{result['actual_duration']:.2f},"
                   f"{result['total_volume']:.2f},{result['min_flow_rate']:.1f},"
                   f"{result['max_flow_rate']:.1f},{result['avg_pressure']:.1f},"
                   f"{result['flow_stability']:.2f}\n")
    
    print(f"Results saved to: {filename}")

def main():
    """Main function to run flow tests."""
    print("OB1 Flow Control Script")
    print("=" * 25)
    
    # Initialize OB1
    channel = c_int32(1)  # Test channel
    instr_id = c_int32(-1)
    
    error = OB1_Initialization('113433_OB1'.encode('ascii'), 0, 0, 0, 0, byref(instr_id))
    if error != 0:
        print(f"Error initializing OB1: {error}")
        return
    
    error = OB1_Add_Sens(instr_id.value, channel, 5, 1, 1, 7, 0)
    print(f"Added sensor with error: {error}")
    
    # Load calibration
    calib_path = r"C:\Users\Public\Documents\Elvesys\ESI\bin\48V444400113433.calib"
    path_buf = create_string_buffer(calib_path.encode('ascii'))
    error = OB1_Calib_Load(instr_id.value, path_buf)
    print(f"Loaded calibration with error: {error}")
    
    # Reset pressure to zero
    error = OB1_Set_Press(instr_id.value, channel, c_double(0))
    
    try:
        # Example 1: Single flow test
        print("\n=== SINGLE FLOW TEST ===")
        result = run_flow_for_time(
            instr_id.value, channel, 
            flow_rate_ul_min=50.0,    # 50 µL/min
            duration_seconds=30.0,    # 30 seconds
            use_pid=True,             # Use PID control
            verbose=True
        )
        
        # Example 2: Multiple flow tests
        print("\n=== MULTIPLE FLOW TESTS ===")
        test_configs = [
            {'flow_rate': 25.0, 'duration': 20.0},   # 25 µL/min for 20 seconds
            {'flow_rate': 50.0, 'duration': 30.0},   # 50 µL/min for 30 seconds
            {'flow_rate': 100.0, 'duration': 15.0},  # 100 µL/min for 15 seconds
        ]
        
        results = run_multiple_tests(
            instr_id.value, channel, test_configs,
            use_pid=True, verbose=True
        )
        
        # Save results
        save_results(results)
        
    finally:
        # Cleanup
        print("\nCleaning up...")
        error = OB1_Set_Press(instr_id.value, channel, c_double(0))
        error = OB1_Destructor(instr_id.value)
        print("Cleanup completed")

if __name__ == "__main__":
    main()
