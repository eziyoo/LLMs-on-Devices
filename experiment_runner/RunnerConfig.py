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
import json  # Added for the new parser

class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))
    
    # --- Experiment Config ---
    name = "s25_llama_thesis_experiment"
    results_output_path = ROOT_DIR / 'results'
    operation_type = OperationType.AUTO
    time_between_runs_in_ms = 3000  # 3 min cool-down between runs

    # --- Device & ADB Settings ---
    ADB_PATH = "adb" 
    DEVICE_ID = "R5CY50M8TDM"  # "192.168.43.227:5555" | "R5CY50M8TDM"
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
                
                # --- Timing & Speed Metrics ---
                'input_token_count',        # int
                'output_token_count',       # int
                'total_token_count',        # int
                
                'prompt_prefill_speed',     # t/s
                'generation_decoder_speed', # t/s
                
                'prefill_latency',          # seconds
                'generation_latency',       # seconds
                'inference_latency',        # seconds
                'time_to_first_token',      # seconds
                
                # --- Energy Metrics ---
                'avg_current',              # Amps
                'avg_voltage',              # Volts
                'avg_power',                # Watts
                'total_energy_consumption', # Joules
                'energy_per_token',         # Joules/Token
                
                # --- Device Stats ---
                'battery_capacity',         # Percentage
                'min_temperature',          # Celsius
                'max_temperature',          # Celsius
                'average_temperature'       # Celsius
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

        # B. Add ALL Model files from the directory
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
        
        article_text = (
            "The World Wide Web (WWW) was invented by British scientist Tim Berners-Lee "
            "in 1989. He was working at CERN, the European Organization for Nuclear "
            "Research, near Geneva, Switzerland. Berners-Lee created the Web to meet "
            "the demand for automatic information-sharing between scientists in "
            "universities and institutes around the world."
            )

        cmd = (
            f"cd {self.REMOTE_DIR} && "
            f"LD_LIBRARY_PATH=. ./llama-cli "
            f"-m {WARMUP_MODEL} "
            f"-p 'Instruct: Summarize the following text.\nText: {article_text}\nOutput:' "
            f"-st "
            f"-v "
            f"-n 128 "
            f"-c 512 -t 8 --temp 0 "
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
        cmd = (
            f"{self.ADB_PATH} -s {self.DEVICE_ID} shell am start-foreground-service "
            f"-n \"com.example.batterymanager_utility/com.example.batterymanager_utility.DataCollectionService\" "
            f"--ei sampleRate 100 "
            f"--es \"dataFields\" \"BATTERY_PROPERTY_CURRENT_NOW,EXTRA_VOLTAGE,BATTERY_PROPERTY_CAPACITY,EXTRA_TEMPERATURE\" "
            f"--ez toCSV False"
        )
        subprocess.run(cmd, shell=True)
        # Allow service to spin up
        time.sleep(2)

    def interact(self, context: RunnerContext) -> None:
        model = context.execute_run["model_file"]
        
        # Define paths
        remote_log_file = "/data/local/tmp/llama_output.txt"
        
        # 1. Clean previous logs on device
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell rm -f {remote_log_file}", shell=True)

        context_text = (
            "The World Wide Web (WWW) was invented by British scientist Tim Berners-Lee "
            "in 1989. He was working at CERN, the European Organization for Nuclear "
            "Research, near Geneva, Switzerland. Berners-Lee created the Web to meet "
            "the demand for automatic information-sharing between scientists in "
            "universities and institutes around the world."
            )
        
        # 2. DYNAMIC PROMPT FORMATTING
        if "gemma" in model.lower():
            final_prompt = (
                f"<start_of_turn>user\n"
                f"Summarize the following text.\nText: {context_text}<end_of_turn>\n"
                f"<start_of_turn>model\n"
            )
        elif "phi-2" in model.lower():
            final_prompt = f"Instruct: Summarize the following text.\n{context_text}\nOutput:"
        elif "llama-3" in model.lower():
            final_prompt = (
                f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
                f"Summarize the following text.\nText: {context_text}<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
        elif "olmoe" in model.lower():
            final_prompt = (
                f"<|endoftext|><|user|>\n"
                f"Summarize the following text.\nText: {context_text}\n"
                f"<|assistant|>\n"
            )
        else:
            final_prompt = (
                f"<|im_start|>user\n"
                f"Summarize the following text.\nText: {context_text}\n"
                f"<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )

        # 5. Cmd
        # Ensure we capture stdout/stderr to the file for the parser to work
        cmd = (
            f"cd {self.REMOTE_DIR} && "
            f"LD_LIBRARY_PATH=. ./llama-cli "
            f"-m {model} "
            f"-p '{final_prompt}' "
            f"-st "
            f"-v "
            f"-n 128 "
            f"-c 512 -t 8 --temp 0 "
            f"> {remote_log_file} 2>&1"
        )
        
        output.console_log(f"--> Running Inference on {model}...")
        
        # Execute blocking call
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell \"{cmd}\"", shell=True)

        # 6. Pull the results
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

        # --- 2. Process Llama Output (Using updated Parser) ---
        llama_metrics = {
            'model_response': '',
            'input_token_count': 0, 'output_token_count': 0, 'total_token_count': 0,
            'prompt_prefill_speed': 0.0, 'generation_decoder_speed': 0.0,
            'prefill_latency': 0.0, 'generation_latency': 0.0, 'inference_latency': 0.0,
            'time_to_first_token': 0.0
        }
        
        if os.path.exists(llama_log_path):
            try:
                # Use the new Robust Parsing Logic
                llama_metrics = self._parse_llama_log_file(str(llama_log_path))
            except Exception as e:
                output.console_log(f"Error parsing llama logs: {e}")

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
                            csv_part = line.split("stats => ")[1].strip()
                            parts = csv_part.split(",")
                            
                            ts = int(parts[0])
                            curr_raw = int(parts[1]) # Unit: µA
                            volt_mV = int(parts[2])  # Unit: mV
                            cap_pct = int(parts[3])  # Unit: %
                            temp_raw = int(parts[4]) # Unit: Tenths of °C

                            # --- UNIT CONVERSION ---
                            time_sec = ts / 1000.0
                            
                            # Current: µA -> Amps. Subtract Baseline (0.10A approx).
                            current_A = max(0, (abs(curr_raw) / 1000000.0) - 0.10)
                            
                            # Voltage: mV -> Volts
                            voltage_V = volt_mV / 1000.0

                            # Temp: Tenths -> Degrees
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
        min_temp = min(temps_c) if temps_c else 0
        max_temp = max(temps_c) if temps_c else 0

        # Energy Per Token
        gen_tokens = llama_metrics.get('output_token_count', 0)
        energy_per_token = total_energy_joules / gen_tokens if gen_tokens > 0 else 0

        # Return Combined Data
        return {
            'model_response': llama_metrics['model_response'],
            
            # Counts
            'input_token_count': llama_metrics['input_token_count'],
            'output_token_count': llama_metrics['output_token_count'],
            'total_token_count': llama_metrics['total_token_count'],

            # Speed
            'prompt_prefill_speed': llama_metrics['prompt_prefill_speed'],
            'generation_decoder_speed': llama_metrics['generation_decoder_speed'],

            # Latency (Parsed as Seconds)
            'prefill_latency': llama_metrics['prefill_latency'],
            'generation_latency': llama_metrics['generation_latency'],
            'inference_latency': llama_metrics['inference_latency'],
            'time_to_first_token': llama_metrics['time_to_first_token'],
            
            # Energy & Device Stats
            'avg_current': round(avg_current, 6),
            'avg_voltage': round(avg_voltage, 4),
            'avg_power': round(avg_power, 4),
            'total_energy_consumption': round(total_energy_joules, 4),
            'energy_per_token': round(energy_per_token, 4),
            'battery_capacity': round(avg_capacity, 2),
            'average_temperature': round(avg_temp, 2),
            'min_temperature': round(min_temp, 2),
            'max_temperature': round(max_temp, 2)
        }
    
    def after_experiment(self):
        output.console_log("All experiments complete.")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell logcat -c", shell=True)
        output.console_log("Closing BatteryManager App...")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell am force-stop com.example.batterymanager_utility", shell=True)
        output.console_log("    [SCREEN] Restoring screen timeout to 2 minutes...")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell settings put system screen_off_timeout 120000", shell=True)

    def _parse_llama_log_file(self, file_path):
        """
        Parses the llama output log file using Regex to extract timing metrics
        and JSON parsing to extract the final clean response.
        """
        metrics = {
            'model_response': '',
            'input_token_count': 0,
            'output_token_count': 0,
            'total_token_count': 0,
            'prompt_prefill_speed': 0.0,
            'generation_decoder_speed': 0.0,
            'prefill_latency': 0.0,
            'generation_latency': 0.0,
            'inference_latency': 0.0,
            'time_to_first_token': 0.0
        }

        # Regex Patterns
        # 1. Prompt Eval: Matches "prompt eval time = ..."
        prompt_pattern = re.compile(r"prompt eval time\s+=\s+(\d+\.\d+)\s+ms\s+/\s+(\d+)\s+tokens\s+\(\s+(\d+\.\d+)\s+ms per token,\s+(\d+\.\d+)\s+tokens per second\)")
        
        # 2. Eval (Generation): Uses (?<!prompt) to ensure we don't match "prompt eval time"
        #    Matches "eval time = ..." but NOT "prompt eval time = ..."
        eval_pattern = re.compile(r"(?<!prompt)\s+eval time\s+=\s+(\d+\.\d+)\s+ms\s+/\s+(\d+)\s+(?:tokens|runs).*?\(\s+(\d+\.\d+)\s+ms per token,\s+(\d+\.\d+)\s+tokens per second\)")
        
        # 3. Total Time
        total_pattern = re.compile(r"total time\s+=\s+(\d+\.\d+)\s+ms")
        
        # 4. Response JSON
        response_pattern = re.compile(r'Parsed message: (\{.*\})')

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

                # 1. Extract Prompt Metrics
                prompt_match = prompt_pattern.search(content)
                if prompt_match:
                    metrics['prefill_latency'] = float(prompt_match.group(1)) / 1000.0  # ms -> s
                    metrics['input_token_count'] = int(prompt_match.group(2))
                    metrics['prompt_prefill_speed'] = float(prompt_match.group(4))

                # 2. Extract Generation Metrics & TTFT
                eval_match = eval_pattern.search(content)
                if eval_match:
                    metrics['generation_latency'] = float(eval_match.group(1)) / 1000.0  # ms -> s
                    metrics['output_token_count'] = int(eval_match.group(2))
                    ms_per_token = float(eval_match.group(3))
                    metrics['generation_decoder_speed'] = float(eval_match.group(4))
                    
                    # Calculate TTFT: Prefill time + time for 1 decode step
                    metrics['time_to_first_token'] = metrics['prefill_latency'] + (ms_per_token / 1000.0)

                # 3. Extract Total Metrics
                total_match = total_pattern.search(content)
                if total_match:
                    metrics['inference_latency'] = float(total_match.group(1)) / 1000.0  # ms -> s
                else:
                    # Fallback if total time line is missing
                    metrics['inference_latency'] = metrics['prefill_latency'] + metrics['generation_latency']

                metrics['total_token_count'] = metrics['input_token_count'] + metrics['output_token_count']
                
                # 4. Extract Model Response (JSON Method)
                response_match = response_pattern.search(content)
                if response_match:
                    json_str = response_match.group(1)
                    try:
                        data = json.loads(json_str)
                        metrics['model_response'] = data.get('content', '')
                    except json.JSONDecodeError:
                        metrics['model_response'] = "Error parsing JSON response content"
                else:
                    # Fallback to simple cleanup if JSON line not found
                    metrics['model_response'] = self._fallback_clean_response(content)

        except FileNotFoundError:
            output.console_log(f"Error: File '{file_path}' not found.")
        
        return metrics

    def _fallback_clean_response(self, full_text):
        """
        Fallback method if the JSON 'Parsed message' line is missing.
        """
        # Remove logs header/footer
        content = re.sub(r"build:.*", "", full_text)
        content = re.sub(r"llama_memory_breakdown_print.*", "", content, flags=re.DOTALL)
        
        # Split by common Prompt endings to find response start
        separators = ["<|im_start|>assistant", "<start_of_turn>model", "Output:"]
        for sep in separators:
            if sep in content:
                content = content.split(sep)[-1]
                break
        
        # Remove CLI artifacts (spinners, timestamps)
        content = re.sub(r'^[\|/\\\-\s]+', '', content)
        content = re.sub(r'^\s*[\d\.]+\s*ms.*', '', content, flags=re.MULTILINE)
        
        return content.strip()