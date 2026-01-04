from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ProgressManager.Output.OutputProcedure import OutputProcedure as output
from os.path import dirname, realpath
from pathlib import Path
import subprocess
import time
import re
import statistics
import os
import glob

class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))
    
    # --- Experiment Config ---
    name = "s25_llama_thesis_experiment"
    results_output_path = ROOT_DIR / 'results'
    operation_type = OperationType.AUTO
    time_between_runs_in_ms = 3000  # 3s cool-down between runs

    # --- Device & ADB Settings ---
    ADB_PATH = "adb" 
    DEVICE_ID = "192.168.43.227:5555"  # Use wireless port: "192.168.43.227:5555" | "R5CY50M8TDM" Samsung S25 Ultra ADB Serial
    REMOTE_DIR = "/data/local/tmp"
    BINARY_NAME = "llama-cli"
    
    # --- Local Paths ---
    LOCAL_LLAMA_BUILD = os.path.expanduser("~/llm_on_device/llama.cpp/build-android/bin")
    LOCAL_MODEL_PATH = "/mnt/d/GoogleDriveMirror/UNI/Thesis/Files/script/models/qwen2-0_5b-instruct-q4_k_m.gguf"

    def __init__(self):
        EventSubscriptionController.subscribe_to_multiple_events([
            (RunnerEvents.BEFORE_EXPERIMENT, self.before_experiment),
            (RunnerEvents.START_RUN, self.start_run),
            (RunnerEvents.START_MEASUREMENT, self.start_measurement),
            (RunnerEvents.INTERACT, self.interact),
            (RunnerEvents.STOP_MEASUREMENT, self.stop_measurement),
            (RunnerEvents.POPULATE_RUN_DATA, self.populate_run_data),
            (RunnerEvents.AFTER_EXPERIMENT, self.after_experiment)
        ])
        self.run_table_model = None
        
        # Ensure results directory exists
        if not os.path.exists(self.results_output_path):
            os.makedirs(self.results_output_path)

    def create_run_table_model(self) -> RunTableModel:
        # Define Factors
        factor_model = FactorModel("model_file", ["qwen2-0_5b-instruct-q4_k_m.gguf"])
        
        self.run_table_model = RunTableModel(
            factors=[factor_model],
            repetitions=50,
            data_columns=[
                'model_response',
                'prompt_prefill_speed',     # t/s
                'generation_decoder_speed', # t/s
                'prefill_latency',          # seconds
                'generation_latency',       # seconds
                'inference_latency',        # seconds
                'time_to_first_token',      # seconds
                'avg_current',              # Amps
                'avg_voltage',              # Volts
                'avg_power',                # Watts
                'total_energy_consumption', # Joules
                'energy_per_token',         # Joules/Token
            ]
        )
        return self.run_table_model

    def before_experiment(self) -> None:
        output.console_log("--> [SETUP] Initializing Device...")
        
        # 1. Clear Logcat
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell logcat -c", shell=True)
        
        # 1.1 Prevent screen from turning off
        output.console_log("    [SCREEN] Setting timeout to max...")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell settings put system screen_off_timeout 2147483647", shell=True)

        # --- SMART FILE SYNC ---
        # Create a list of all files we need on the device
        files_to_sync = []

        # A. Find all local library files (lib*.so) using glob
        if os.path.exists(self.LOCAL_LLAMA_BUILD):
            lib_files = glob.glob(os.path.join(self.LOCAL_LLAMA_BUILD, "lib*.so"))
            files_to_sync.extend(lib_files)
            
            # B. Add the main binary (llama-cli)
            files_to_sync.append(os.path.join(self.LOCAL_LLAMA_BUILD, self.BINARY_NAME))
        else:
             output.console_log(f"--> WARNING: Local build path not found: {self.LOCAL_LLAMA_BUILD}")

        # C. Add the Model file
        files_to_sync.append(self.LOCAL_MODEL_PATH)
        
        output.console_log(f"--> [SYNC] Verifying {len(files_to_sync)} files on device...")

        # Loop through every file and check if it exists on the phone
        for local_path in files_to_sync:
            # Extract just the filename (e.g., "libggml.so" or "model.gguf")
            filename = os.path.basename(local_path)
            remote_path = f"{self.REMOTE_DIR}/{filename}"
            
            # ADB Command: Check if file exists ([ -f path ])
            # Returns 0 if found, 1 if missing
            check_cmd = f"{self.ADB_PATH} -s {self.DEVICE_ID} shell [ -f \"{remote_path}\" ]"
            
            # Run silently (stdout/stderr to DEVNULL)
            result = subprocess.run(check_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if result.returncode == 0:
                output.console_log(f"    [SKIP] Found {filename} on device.")
            else:
                output.console_log(f"    [PUSH] Pushing {filename}...")
                # Push the file (using quotes for safety)
                subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} push \"{local_path}\" {self.REMOTE_DIR}/", shell=True)

        # 4. Make binary executable (Always run this to be safe)
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell chmod +x {self.REMOTE_DIR}/{self.BINARY_NAME}", shell=True)

        # 5. Launch Spy App
        #output.console_log("    Launching BatteryManager App...")
        #subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell am start -n \"com.example.batterymanager_utility/com.example.batterymanager_utility.MainActivity\" -a android.intent.action.MAIN -c android.intent.category.LAUNCHER", shell=True)
        #time.sleep(2)

        # 6. Grant Permissions
        output.console_log("    Granting permissions...")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell pm grant com.example.batterymanager_utility android.permission.POST_NOTIFICATIONS", shell=True)
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell dumpsys deviceidle whitelist +com.example.batterymanager_utility", shell=True)

        # 7. Warm-Up phase
        output.console_log("--> [WARMUP] Running one inference pass to warm up caches...")
        
        # Extract the model filename from your local path
        model_filename = os.path.basename(self.LOCAL_MODEL_PATH)
        warmup_prompt = "Write a story about a robot."
        
        # Construct the command
        # Note: We send output to /dev/null because we don't need to save the warm-up story
        cmd = (
            f"cd {self.REMOTE_DIR} && "
            f"LD_LIBRARY_PATH=. ./llama-cli "
            f"-m {model_filename} "
            f"-p '{warmup_prompt}' "
            f"-st "                  # Single-turn mode
            f"-n 128 "               # Same token limit as experiment
            f"-c 2048 -t 8 --temp 0 " # Default to 8 threads (same as your logic)
            f"> /dev/null 2>&1"      # Discard output to keep logs clean
        )

        # Run the command
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell \"{cmd}\"", shell=True)
        output.console_log("--> [WARMUP] Done.")

        

        output.console_log("--> [SETUP] Done.")

    def start_run(self, context: RunnerContext) -> None:
        # Clear logcat to ensure clean slate for this specific run
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell logcat -c", shell=True)

    def start_measurement(self, context: RunnerContext) -> None:
        output.console_log("--> Starting BatteryManager Service...")
        # Start service to log 100ms intervals
        # Note: We requested only CURRENT and VOLTAGE here
        cmd = (
            f"{self.ADB_PATH} -s {self.DEVICE_ID} shell am start-foreground-service "
            f"-n \"com.example.batterymanager_utility/com.example.batterymanager_utility.DataCollectionService\" "
            f"--ei sampleRate 100 "
            f"--es \"dataFields\" \"BATTERY_PROPERTY_CURRENT_NOW,EXTRA_VOLTAGE\" "
            f"--ez toCSV False"
        )
        subprocess.run(cmd, shell=True)

    def interact(self, context: RunnerContext) -> None:
        model = context.execute_run["model_file"]
        
        # Single file for merged output (Stdout + Stderr)
        remote_log_file = "/data/local/tmp/llama_output.txt"
        
        # 1. Clean previous file
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell rm -f {remote_log_file}", shell=True)

        prompt_text = "Write a story about a robot."
        
        # 2. Construct Command
        # FIX: Added '-t 8' to set default threads since variable was removed.
        cmd = (
            f"cd {self.REMOTE_DIR} && "
            f"LD_LIBRARY_PATH=. ./llama-cli "
            f"-m {model} "
            f"-p '{prompt_text}' "
            f"-st "                  # Single-turn mode
            f"-n 128 "               # Fixed token limit
            f"-c 2048 -t 8 --temp 0 "
            f"> {remote_log_file} 2>&1"  # Merge streams
        )
        
        output.console_log(f"--> Running Inference on {model}...")
        
        # Execute blocking call
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell \"{cmd}\"", shell=True)

        # 3. Pull the single file to local context directory
        local_log_file = context.run_dir / "llama_output.txt"
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} pull {remote_log_file} \"{local_log_file}\"", shell=True)

    def stop_measurement(self, context: RunnerContext) -> None:
        output.console_log("--> Stopping BatteryManager Service...")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell am stopservice com.example.batterymanager_utility/com.example.batterymanager_utility.DataCollectionService", shell=True)
        
        # Dump logcat (Battery logs) to file
        run_log_path = context.run_dir / "run_logcat.txt"
        with open(run_log_path, "w") as f:
            subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell logcat -d", stdout=f, shell=True)

    def populate_run_data(self, context: RunnerContext):
        # --- 1. Load Paths ---
        battery_log_path = context.run_dir / "run_logcat.txt"
        llama_log_path = context.run_dir / "llama_output.txt"

        # --- 2. Process Llama Output (Single File) ---
        model_response = ""
        llama_metrics = {}
        
        if os.path.exists(llama_log_path):
            with open(llama_log_path, "r", encoding="utf-8", errors="ignore") as f:
                full_text = f.read()
                llama_metrics = self._parse_llama_timings(full_text)
                model_response = self._clean_story_from_logs(full_text)

        # --- 3. Process Battery Logs (Trapezoidal Rule) ---
        power_readings = []
        currents_A = []
        voltages_V = []
        
        total_energy_joules = 0.0
        prev_time = None
        prev_power = None
        
        if os.path.exists(battery_log_path):
            with open(battery_log_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "BatteryMgr:DataCollectionService: stats =>" in line:
                        try:
                            # Parse CSV: "stats => timestamp, current, voltage"
                            # Note: We removed Capacity and Temp from start_measurement
                            csv_part = line.split("stats => ")[1].strip()
                            parts = csv_part.split(",")
                            
                            ts = int(parts[0])
                            curr_raw = int(parts[1]) # Unit: µA (Micro)
                            volt_mV = int(parts[2])  # Unit: mV (Milli)

                            # --- UNIT CONVERSION ---
                            time_sec = ts / 1000.0
                            
                            # Current: µA -> Amps (Divide by 1,000,000)
                            current_A = abs(curr_raw) / 1000000.0 
                            
                            # Voltage: mV -> Volts (Divide by 1,000)
                            voltage_V = volt_mV / 1000.0        

                            # B. Subtract Baseline (Find Model's Draw)
                            # We use max(0, ...) to ensure we don't get negative power if noise dips below baseline
                            current_A_n = max(0, current_A - 0.10)  
                            
                            power_W = current_A_n * voltage_V

                            currents_A.append(current_A_n)
                            voltages_V.append(voltage_V)
                            power_readings.append(power_W)

                            # Trapezoidal Integration
                            if prev_time is not None:
                                dt = time_sec - prev_time
                                if dt > 0:
                                    # Average power over this interval
                                    avg_p = (power_W + prev_power) / 2
                                    total_energy_joules += avg_p * dt
                            
                            prev_time = time_sec
                            prev_power = power_W
                        except (ValueError, IndexError):
                            continue

        # --- 4. Aggregate Results ---
        avg_current = statistics.mean(currents_A) if currents_A else 0
        avg_voltage = statistics.mean(voltages_V) if voltages_V else 0
        avg_power = statistics.mean(power_readings) if power_readings else 0

        # Energy Per Token
        gen_tokens = llama_metrics.get('output_tokens', 128)
        energy_per_token = total_energy_joules / gen_tokens if gen_tokens > 0 else 0

        return {
            'model_response': model_response,
            'prompt_prefill_speed': llama_metrics.get('prompt_tps', 0),
            'generation_decoder_speed': llama_metrics.get('gen_tps', 0),
            'prefill_latency': llama_metrics.get('prefill_latency', 0),
            'generation_latency': llama_metrics.get('gen_latency', 0),
            'inference_latency': llama_metrics.get('inference_latency', 0),
            'time_to_first_token': llama_metrics.get('ttft', 0),
            
            'avg_current': round(avg_current, 6), # High precision for Amps
            'avg_voltage': round(avg_voltage, 4),
            'avg_power': round(avg_power, 4),
            'total_energy_consumption': round(total_energy_joules, 4),
            'energy_per_token': round(energy_per_token, 4),
        }
    
    def after_experiment(self):
        output.console_log("All experiments complete.")
        
        # Clear logs and close app
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell logcat -c", shell=True)
        
        # Close BatteryManager
        output.console_log("Closing BatteryManager App...")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell am force-stop com.example.batterymanager_utility", shell=True)

        # RESTORE SCREEN ---
        output.console_log("    [SCREEN] Restoring screen timeout to 2 minutes...")
        # Reset timeout to 120000ms (2 minutes)
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell settings put system screen_off_timeout 120000", shell=True)
        

        time.sleep(1)

    def _parse_llama_timings(self, log_text):
        """Extracts TPS and calculates latencies."""
        data = {
            'prompt_tps': 0.0,
            'gen_tps': 0.0,
            'prefill_latency': 0.0,
            'gen_latency': 0.0,
            'inference_latency': 0.0,
            'ttft': 0.0,
            'output_tokens': 128,
            'input_tokens': 8
        }
        
        p_match = re.search(r"Prompt:\s+(\d+\.\d+)\s+t/s", log_text)
        g_match = re.search(r"Generation:\s+(\d+\.\d+)\s+t/s", log_text)

        if p_match: data['prompt_tps'] = float(p_match.group(1))
        if g_match: data['gen_tps'] = float(g_match.group(1))

        if data['prompt_tps'] > 0:
            data['prefill_latency'] = data['input_tokens'] / data['prompt_tps']
        if data['gen_tps'] > 0:
            data['gen_latency'] = data['output_tokens'] / data['gen_tps']
            data['ttft'] = data['prefill_latency'] + (1 / data['gen_tps'])

        data['inference_latency'] = data['prefill_latency'] + data['gen_latency']
        return data

    def _clean_story_from_logs(self, full_text):
            """
            Aggressively filters system logs, spinners, menus, and speed metrics.
            """
            clean_lines = []
            
            for line in full_text.split('\n'):
                # 1. Skip System Info & Menu Commands
                if any(x in line for x in [
                    "build ", "model ", "modalities :", "available commands:", 
                    "/exit", "/regen", "/clear", "/read", 
                    "llama_memory", "Exiting...", "Executing:", "Loading model..."
                ]):
                    continue
                
                # 2. Skip ASCII Art (Block chars and Mojibake)
                if "█" in line or "▄" in line or "▀" in line or "â–€" in line:
                    continue
                
                # 3. Skip the Prompt Echo
                if line.strip().startswith("> "):
                    continue

                # 4. Skip Speed Metrics (The line you want to remove)
                # Catches: "[ Prompt: 84.0 t/s | Generation: 50.0 t/s ]"
                if "t/s" in line and "Prompt:" in line:
                    continue

                # 5. Clean Loading Spinner (The "| - \" animation)
                line = line.replace('\x08', '') # Remove backspaces
                line = re.sub(r'^[\|\/\-\\]+\s*', '', line) # Remove spinner chars

                # 6. Skip Empty Lines
                if not line.strip():
                    continue
                    
                clean_lines.append(line)
                
            return "\n".join(clean_lines).strip()