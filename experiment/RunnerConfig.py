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
import os
import glob
import sys

# Experiment-Runner loads this file by path, so make the sibling modules importable.
sys.path.insert(0, dirname(realpath(__file__)))
from log_parsers import parse_run  # noqa: E402
from settings import MODEL_RUN_IDS, ROOT_DIR, load_settings  # noqa: E402

SETTINGS = load_settings()
MODEL = SETTINGS.get("run", "model")


class RunnerConfig:
    ROOT_DIR = ROOT_DIR

    # --- Experiment Config ---
    name = MODEL_RUN_IDS.get(MODEL, Path(MODEL).stem)
    results_output_path = ROOT_DIR / 'results'
    operation_type = OperationType.AUTO
    time_between_runs_in_ms = SETTINGS.getint("run", "cooldown_seconds", fallback=200) * 1000  # cool-down between runs

    # --- Device & ADB Settings ---
    ADB_PATH = SETTINGS.get("device", "adb_path", fallback="adb")
    DEVICE_ID = SETTINGS.get("device", "device_id")
    REMOTE_DIR = SETTINGS.get("device", "remote_dir", fallback="/data/local/tmp")
    BINARY_NAME = "llama-cli"

    # --- Local Paths ---
    LOCAL_LLAMA_BUILD = os.path.expanduser(SETTINGS.get("paths", "llama_build_dir"))
    LOCAL_MODEL_PATH = os.path.expanduser(SETTINGS.get("paths", "model_dir"))

    # --- Measurement ---
    REPETITIONS = SETTINGS.getint("run", "repetitions", fallback=30)
    BASELINE_CURRENT_A = SETTINGS.getfloat("run", "baseline_current_a", fallback=0.10)

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
        # One model per round: the model under test comes from config.ini
        factor_model = FactorModel("model_file", [MODEL])

        self.run_table_model = RunTableModel(
            factors=[factor_model],
            repetitions=self.REPETITIONS,
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
                'min_battery_capacity',     # Percentage
                'max_battery_capacity',     # Percentage
                'min_temperature',          # Celsius
                'max_temperature',          # Celsius
                'average_temperature',      # Celsius

                # --- Memory Stats ---
                'peak_memory',              # MiB
                'model_weight',             # MiB
                'KV_cache',                 # MiB
                'context_RAM',              # MiB
                'compute_RAM'               # MiB
            ]
        )
        return self.run_table_model

    def before_experiment(self) -> None:
        output.console_log(f"--> [SETUP] Initializing Device for {MODEL}...")

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

        # B. Add the model under test
        model_file = os.path.join(self.LOCAL_MODEL_PATH, MODEL)
        if not os.path.isfile(model_file):
            output.console_log(f"--> WARNING: {model_file} not found locally (fine if it is already on the device)")
        files_to_sync.append(model_file)

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

        # 7. Warm-Up phase (with the model under test)
        WARMUP_MODEL = MODEL

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
            f"-n 100 --ignore-eos "
            f"-c 512 -t 8 --temp 0 "
            f"> /dev/null 2>&1"
        )

        # Execute
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell \"{cmd}\"", shell=True)
        output.console_log("--> [WARMUP] Done.")
        output.console_log("--> [SETUP] Done.")
        output.console_log("--> Waiting for 200 seconds...")
        time.sleep(200)

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
            stop_tokens = [107]

        elif "phi-2" in model.lower():
            final_prompt = f"Summarize the following text.\n{context_text}\nOutput:"
            stop_tokens = [50256]

        elif "llama-3" in model.lower():
            final_prompt = (
                f"<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
                f"Summarize the following text.\nText: {context_text}<|eot_id|>"
                f"<|start_header_id|>assistant<|end_header_id|>\n\n"
            )
            stop_tokens = [128009]

        elif "olmoe" in model.lower():
            final_prompt = (
                f"<|endoftext|><|user|>\n"
                f"Summarize the following text.\nText: {context_text}\n"
                f"<|assistant|>\n"
            )
            stop_tokens = [50279]

        else:
            final_prompt = (
                f"<|im_start|>user\n"
                f"Summarize the following text.\nText: {context_text}\n"
                f"<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )
            stop_tokens = [151643, 151645]

        bias_args = " ".join([f"--logit-bias {id}-inf" for id in stop_tokens])
        # 5. Cmd
        # Ensure we capture stdout/stderr to the file for the parser to work
        cmd = (
            f"cd {self.REMOTE_DIR} && "
            f"LD_LIBRARY_PATH=. ./llama-cli "
            f"-m {model} "
            f"-p '{final_prompt}' "
            f"-st "
            f"-v "
            f"-n 100 "
            f"--ignore-eos "
            f"{bias_args} "
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
        # Parse llama_output.txt (timings, memory, response) and run_logcat.txt (energy, trapezoidal rule)
        return parse_run(context.run_dir, self.BASELINE_CURRENT_A, log=output.console_log)

    def after_experiment(self):
        output.console_log("All experiments complete.")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell logcat -c", shell=True)
        output.console_log("Closing BatteryManager App...")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell am force-stop com.example.batterymanager_utility", shell=True)
        output.console_log("    [SCREEN] Restoring screen timeout to 2 minutes...")
        subprocess.run(f"{self.ADB_PATH} -s {self.DEVICE_ID} shell settings put system screen_off_timeout 120000", shell=True)
