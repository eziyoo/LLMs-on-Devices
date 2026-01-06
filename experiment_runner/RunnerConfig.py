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
    time_between_runs_in_ms = 180000  # 3 min cool-down between runs

    # --- Device & ADB Settings ---
    ADB_PATH = "adb" 
    DEVICE_ID = "192.168.43.35:5555"  # Use wireless port: "192.168.43.227:5555" | "R5CY50M8TDM" Samsung S25 Ultra ADB Serial
    REMOTE_DIR = "/data/local/tmp"
    BINARY_NAME = "llama-cli"
    
    # --- Local Paths ---
    LOCAL_LLAMA_BUILD = os.path.expanduser("~/llm_on_device/llama.cpp/build-android/bin")
    LOCAL_MODEL_PATH = "/mnt/d/GoogleDriveMirror/UNI/Thesis/Files/script/models"

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
        factor_model = FactorModel("model_file", 
                                   [
                                       "qwen2-0_5b-instruct-q4_k_m.gguf",
                                       "qwen2.5-1.5b-instruct-q4_k_m.gguf",
                                       "phi-2.Q4_K_M.gguf",
                                       "qwen2.5-3b-instruct-q4_k_m.gguf",
                                       "qwen2.5-7b-instruct-q4_k_m.gguf",
                                       "OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf",
                                       "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
                                       "gemma-2-9b-it-Q4_K_M.gguf"
                                   ]
                                   )
        
        self.run_table_model = RunTableModel(
            factors=[factor_model],
            repetitions=1,
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
                'battery_capacity',         # Percentage
                'battery_temperature'       # Celsius
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
        files_to_sync = []

        # A. Find all local library files (lib*.so)
        if os.path.exists(self.LOCAL_LLAMA_BUILD):
            lib_files = glob.glob(os.path.join(self.LOCAL_LLAMA_BUILD, "lib*.so"))
            files_to_sync.extend(lib_files)
            files_to_sync.append(os.path.join(self.LOCAL_LLAMA_BUILD, self.BINARY_NAME))
        else:
             output.console_log(f"--> WARNING: Local build path not found: {self.LOCAL_LLAMA_BUILD}")

        # B. Add ALL Model files from the directory (So they are ready for the main experiment)
        if os.path.isdir(self.LOCAL_MODEL_PATH):
            model_files = glob.glob(os.path.join(self.LOCAL_MODEL_PATH, "*.gguf"))
            if not model_files:
                output.console_log(f"--> WARNING: No .gguf files found in {self.LOCAL_MODEL_PATH}")
            files_to_sync.extend(model_files)
        else:
            files_to_sync.append(self.LOCAL_MODEL_PATH)
        
        output.console_log(f"--> [SYNC] Verifying {len(files_to_sync)} files on device...")

        # Loop through every file to sync
        for local_path in files_to_sync:
            filename = os.path.basename(local_path)
            remote_path = f"{self.REMOTE_DIR}/{filename}"
            
            # Check if file exists on device
            check_cmd = f"{self.ADB_PATH} -s {self.DEVICE_ID} shell [ -f \"{remote_path}\" ]"
            result = subprocess.run(check_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            if result.returncode == 0:
                output.console_log(f"    [SKIP] Found {filename} on device.")
            else:
                output.console_log(f"    [PUSH] Pushing {filename}...")
                subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} push \"{local_path}\" {self.REMOTE_DIR}/", shell=True)

        # 4. Make binary executable
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell chmod +x {self.REMOTE_DIR}/{self.BINARY_NAME}", shell=True)

        # 6. Grant Permissions
        output.console_log("    Granting permissions...")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell pm grant com.example.batterymanager_utility android.permission.POST_NOTIFICATIONS", shell=True)
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell dumpsys deviceidle whitelist +com.example.batterymanager_utility", shell=True)

        # 7. Warm-Up phase
        WARMUP_MODEL = "qwen2-0_5b-instruct-q4_k_m.gguf"
        
        warmup_prompt = "Instruct: Write a story about a robot.\\nOutput:"
        cmd = (
            f"cd {self.REMOTE_DIR} && "
            f"LD_LIBRARY_PATH=. ./llama-cli "
            f"-m {WARMUP_MODEL} "
            f"-p '{warmup_prompt}' "
            f"-st "
            f"-n 128 "
            f"-c 2048 -t 8 --temp 0 "
            f"> /dev/null 2>&1"
        )
        
        # Execute
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell \"{cmd}\"", shell=True)
        output.console_log("--> [WARMUP] Done.")

        output.console_log("--> [SETUP] Done.")

    def start_run(self, context: RunnerContext) -> None:
        # Clear logcat to ensure clean slate for this specific run
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell logcat -c", shell=True)

    def start_measurement(self, context: RunnerContext) -> None:
        output.console_log("--> Starting BatteryManager Service...")
        # Start service to log 100ms intervals
        # Requesting CURRENT, VOLTAGE, CAPACITY, and TEMPERATURE
        cmd = (
            f"{self.ADB_PATH} -s {self.DEVICE_ID} shell am start-foreground-service "
            f"-n \"com.example.batterymanager_utility/com.example.batterymanager_utility.DataCollectionService\" "
            f"--ei sampleRate 100 "
            f"--es \"dataFields\" \"BATTERY_PROPERTY_CURRENT_NOW,EXTRA_VOLTAGE,BATTERY_PROPERTY_CAPACITY,EXTRA_TEMPERATURE\" "
            f"--ez toCSV False"
        )
        subprocess.run(cmd, shell=True)

    def interact(self, context: RunnerContext) -> None:
        model = context.execute_run["model_file"]
        
        # Single file for merged output (Stdout + Stderr)
        remote_log_file = "/data/local/tmp/llama_output.txt"
        
        # 1. Clean previous file
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell rm -f {remote_log_file}", shell=True)

        prompt_text = "Instruct: Write a story about a robot.\\nOutput:"
        
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
        capacities_pct = []
        temps_c = []
        
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
                            cap_pct = int(parts[3])  # Unit: %
                            temp_raw = int(parts[4]) # Unit: Tenths of °C

                            # --- UNIT CONVERSION ---
                            time_sec = ts / 1000.0
                            
                            # A. Current: µA -> Amps (Divide by 1,000,000)
                            # B. Subtract Baseline (Find Model's Draw)
                            # We use max(0, ...) to ensure we don't get negative power if noise dips below baseline
                            current_A = max(0, (abs(curr_raw) / 1000000.0) - 0.10)
                            
                            # Voltage: mV -> Volts (Divide by 1,000)
                            voltage_V = volt_mV / 1000.0

                            # Convert tenths to degrees
                            temp_C_val = temp_raw / 10.0  
                            
                            power_W = current_A * voltage_V

                            currents_A.append(current_A)
                            voltages_V.append(voltage_V)
                            power_readings.append(power_W)
                            capacities_pct.append(cap_pct)
                            temps_c.append(temp_C_val)

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
        avg_capacity = statistics.mean(capacities_pct) if capacities_pct else 0
        avg_temp = statistics.mean(temps_c) if temps_c else 0

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
            'battery_capacity': round(avg_capacity, 2),
            'battery_temperature': round(avg_temp, 2)
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
            'input_tokens': 13
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
        Aggressively filters system logs, spinners, menus, speed metrics,
        and chat prefixes (Assistant:, Output:, etc.).
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
            
            # 2. Skip ASCII Art (Block chars)
            if "█" in line or "▄" in line or "▀" in line or "â–€" in line:
                continue
            
            # 3. Skip the Prompt Echo (> Instruct: ...)
            if line.strip().startswith("> "):
                continue

            # 4. Skip Speed Metrics
            if "t/s" in line and "Prompt:" in line:
                continue

            # 5. Clean Loading Spinner
            line = line.replace('\x08', '') 
            line = re.sub(r'^[\|\/\-\\]+\s*', '', line) 

            # --- NEW FIXES START HERE ---
            
            # 6. Remove common prefixes if they appear at the start of the line
            # This turns "Assistant: Once upon..." into "Once upon..."
            # and removes standalone "Output:" lines.
            line = re.sub(r'^(Assistant|Output|AI|Bot):\s*', '', line, flags=re.IGNORECASE)

            # --- NEW FIXES END HERE ---

            # 7. Skip Empty Lines (must be done after stripping prefixes)
            if not line.strip():
                continue
                
            clean_lines.append(line)
            
        return "\n".join(clean_lines).strip()