import subprocess
import time
import os
import statistics
import re

# --- CONFIGURATION ---
ADB_PATH = "adb"
DEVICE_ID = "192.168.43.227:5555"  # Samsung S25 Ultra
DURATION_SEC = 3600        # 30 Minutes
REMOTE_DIR = "/data/local/tmp"

def run_adb(cmd):
    return subprocess.run(f"{ADB_PATH} -s {DEVICE_ID} shell {cmd}", shell=True, capture_output=True, text=True)

def measure_baseline():
    print(f"--> [BASELINE] Starting 30-minute idle measurement on {DEVICE_ID}...")
    
    # 1. Clear Logs & Wake Screen (Ensure consistent idle state)
    run_adb("logcat -c")
    run_adb("input keyevent 224") # Wake up
    run_adb("settings put system screen_off_timeout 2147483647") # Keep screen on

    # 2. Start Service
    print("--> Starting BatteryManager...")
    cmd = (
        "am start-foreground-service "
        "-n \"com.example.batterymanager_utility/com.example.batterymanager_utility.DataCollectionService\" "
        "--ei sampleRate 100 "
        "--es \"dataFields\" \"BATTERY_PROPERTY_CURRENT_NOW,EXTRA_VOLTAGE\" "
        "--ez toCSV False"
    )
    run_adb(cmd)

    # 3. Wait 30 Minutes
    print(f"--> Waiting {DURATION_SEC} seconds (30 min)... Do not touch the phone.")
    try:
        for remaining in range(DURATION_SEC, 0, -10):
            print(f"    Time remaining: {remaining}s...", end='\r')
            time.sleep(10)
    except KeyboardInterrupt:
        print("\n--> Measurement cancelled by user.")

    # 4. Stop Service
    print("\n--> Stopping service...")
    run_adb("am stopservice com.example.batterymanager_utility/com.example.batterymanager_utility.DataCollectionService")
    
    # 5. Save Logs
    print("--> Pulling logs...")
    local_log = "baseline_log.txt"
    if os.path.exists(local_log): os.remove(local_log)
    
    # Dump logcat to file
    with open(local_log, "w") as f:
        subprocess.run(f"{ADB_PATH} -s {DEVICE_ID} shell logcat -d", shell=True, stdout=f)

    # 6. Parse and Calculate
    process_logs(local_log)
    
    # Restore screen timeout (2 mins)
    run_adb("settings put system screen_off_timeout 120000")

def process_logs(filename):
    currents = []
    voltages = []
    
    with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if "BatteryMgr:DataCollectionService: stats =>" in line:
                try:
                    # Parse: stats => timestamp, current, voltage
                    csv_part = line.split("stats => ")[1].strip()
                    parts = csv_part.split(",")
                    
                    curr_raw = int(parts[1]) # MicroAmps
                    volt_mV = int(parts[2])  # MilliVolts
                    
                    # Convert to Standard Units
                    current_A = abs(curr_raw) / 1e6
                    voltage_V = volt_mV / 1000.0
                    
                    currents.append(current_A)
                    voltages.append(voltage_V)
                except:
                    continue

    if currents:
        avg_current = statistics.mean(currents)
        avg_voltage = statistics.mean(voltages)
        avg_power = avg_current * avg_voltage
        
        print("\n" + "="*40)
        print(f"BASELINE RESULTS (Average over {len(currents)} samples)")
        print("="*40)
        print(f"Avg Voltage: {avg_voltage:.4f} V")
        print(f"Avg Current: {avg_current:.6f} A  <-- COPY THIS")
        print(f"Avg Power:   {avg_power:.4f} W")
        print("="*40)
        print("Update your RunnerConfig with these values.")
    else:
        print("\n--> ERROR: No data found in logs.")

if __name__ == "__main__":
    measure_baseline()