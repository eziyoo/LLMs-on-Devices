import subprocess, time, re, json, statistics
from pathlib import Path
from os.path import dirname, realpath
from typing import Dict, Any, Optional

from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ProgressManager.Output.OutputProcedure import OutputProcedure as output


# ============================
# TASK → DATASET → METRIC MAP
# ============================

TASK_SPECS = {
    "text_generation": {
        "dataset": "wikitext_2",
        "metric": "bertscore",
        "prompt_template": "Continue the following text:\n{input}\n"
    },
    "question_answering": {
        "dataset": "SQuAD",
        "metric": "bertscore",
        "prompt_template": "Answer the question:\nContext: {context}\nQuestion: {question}\nAnswer:"
    },
    "text_classification": {
        "dataset": "SST_2",
        "metric": "auc_roc",
        "prompt_template": "Classify the sentiment as positive or negative:\nText: {input}\nSentiment:"
    },
    "summarization": {
        "dataset": "CNN_DailyMail",
        "metric": "bertscore",
        "prompt_template": "Summarize the following article:\n{input}\nSummary:"
    },
    "translation": {
        "dataset": "WMT19",
        "metric": "comet",
        "prompt_template": "Translate the following English text into German:\n{input}\nGerman:"
    }
}


class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))
    name = "llama_android_full_experiment"
    results_output_path = ROOT_DIR / "experiments"
    operation_type = OperationType.AUTO

    time_between_runs_in_ms = 2000

    def __init__(self):
        EventSubscriptionController.subscribe_to_multiple_events([
            (RunnerEvents.BEFORE_EXPERIMENT, self.before_experiment),
            (RunnerEvents.BEFORE_RUN, self.before_run),
            (RunnerEvents.START_RUN, self.start_run),
            (RunnerEvents.START_MEASUREMENT, self.start_measurement),
            (RunnerEvents.INTERACT, self.interact),
            (RunnerEvents.STOP_MEASUREMENT, self.stop_measurement),
            (RunnerEvents.STOP_RUN, self.stop_run),
            (RunnerEvents.POPULATE_RUN_DATA, self.populate_run_data),
            (RunnerEvents.AFTER_EXPERIMENT, self.after_experiment)
        ])
        output.console_log("Loaded full custom config")

    # ============================
    # DEFINE EXPERIMENT FACTORS
    # ============================

    def create_run_table_model(self) -> RunTableModel:

        model_factor = FactorModel(
            "model", [
                "qwen2-0_5b-instruct-q4_k_m.gguf",
                "qwen2.5-1.5b-instruct-q4_k_m.gguf",
                "phi-2.Q4_K_M.gguf",
                "qwen2.5-3b-instruct-q4_k_m.gguf",
                "OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf",
                "qwen2.5-7b-instruct-q4_k_m.gguf",
                "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
                "gemma-2-9b-it-Q4_K_M.gguf",
            ]
        )

        task_factor = FactorModel(
            "task", [
                "text_generation",
                "question_answering",
                "text_classification",
                "summarization",
                "translation"
            ]
        )

        threads_factor = FactorModel("threads", [2, 4, 6])

        return RunTableModel(
            factors=[model_factor, task_factor, threads_factor],
            repetitions=2,
            data_columns=[
                "model_load_ms",
                "ttft_ms",
                "prefill_ms",
                "decode_ms",
                "tps",
                "total_latency_ms",
                "peak_ram_kb",
                "cpu_usage",
                "battery_temp_c",
                "battery_current_ma",
                "battery_voltage_v",
                "energy_joules",
                "energy_per_token",
                "thermal_throttle_freq_mhz"
            ]
        )

    # ============================
    # EXPERIMENT LIFECYCLE
    # ============================

    def before_experiment(self):
        output.console_log("Pushing binaries + models to device…")

        subprocess.run("adb push build-android/bin/llama-cli /data/local/tmp/", shell=True)
        subprocess.run("adb push build-android/bin/llama-bench /data/local/tmp/", shell=True)
        subprocess.run("adb push build-android/bin/lib*.so /data/local/tmp/", shell=True)
        subprocess.run("adb push models/*.gguf /data/local/tmp/models/", shell=True)

        subprocess.run("adb shell chmod +x /data/local/tmp/llama-cli", shell=True)
        subprocess.run("adb shell chmod +x /data/local/tmp/llama-bench", shell=True)

    def before_run(self):
        output.console_log("Clearing caches & resetting thermal state…")
        subprocess.run("adb shell sync; adb shell echo 3 > /proc/sys/vm/drop_caches", shell=True)

    def start_run(self, context: RunnerContext):
        output.console_log(f"▶ Starting run: {context.current_run_name}")

    def start_measurement(self, context: RunnerContext):
        context.experiment_data["start_global"] = time.time()

    # ============================
    # MAIN INFERENCE PHASE
    # ============================

    def interact(self, context: RunnerContext):
        run = context.current_run

        model = run["model"]
        task = run["task"]
        threads = run["threads"]

        task_spec = TASK_SPECS[task]
        metric = task_spec["metric"]

        # Load correct dataset sample
        dataset_path = self.ROOT_DIR / "datasets" / task_spec["dataset"]
        with open(dataset_path / "sample.json") as f:
            sample = json.load(f)

        # Generate prompt
        prompt = task_spec["prompt_template"].format(**sample)

        # Push prompt to phone
        with open("/tmp/prompt.txt", "w") as f:
            f.write(prompt)
        subprocess.run("adb push /tmp/prompt.txt /data/local/tmp/prompt.txt", shell=True)

        # Run llama.cpp on-device
        adb_cmd = (
            f'adb shell "cd /data/local/tmp && '
            f'LD_LIBRARY_PATH=. ./llama-cli '
            f'-m models/{model} '
            f'-t {threads} '
            f'--prompt-file prompt.txt '
            f'--n-predict 128"'
        )

        context.experiment_data["raw_output"] = subprocess.getoutput(adb_cmd)

        # Save end time
        context.experiment_data["end_global"] = time.time()

    def stop_measurement(self, context: RunnerContext):
        pass

    def stop_run(self, context: RunnerContext):
        output.console_log("Cooling device for 30s…")
        time.sleep(30)

    # ============================
    # METRIC EXTRACTORS
    # ============================

    def get_system_metrics(self):
        metrics = {}

        # CPU usage
        cpu_raw = subprocess.getoutput('adb shell top -b -n 1 | grep llama')
        cpu_vals = re.findall(r'\s(\d+)%\s', cpu_raw)
        metrics["cpu_usage"] = int(cpu_vals[0]) if cpu_vals else None

        # RAM usage
        pid = subprocess.getoutput("adb shell pidof llama-cli")
        meminfo = subprocess.getoutput(f"adb shell dumpsys meminfo {pid}")
        rss = re.search(r"TOTAL:\s+(\d+)", meminfo)
        metrics["peak_ram_kb"] = int(rss.group(1)) if rss else None

        # battery temp
        temp_raw = subprocess.getoutput("adb shell dumpsys battery | grep temperature")
        t = re.findall(r"(\d+)", temp_raw)
        metrics["battery_temp_c"] = float(t[0]) / 10 if t else None

        # current (mA)
        cur = subprocess.getoutput("adb shell cat /sys/class/power_supply/battery/current_now")
        metrics["battery_current_ma"] = float(cur) / 1000 if cur else None

        # voltage (V)
        volt = subprocess.getoutput("adb shell cat /sys/class/power_supply/battery/voltage_now")
        metrics["battery_voltage_v"] = float(volt) / 1_000_000 if volt else None

        # CPU frequency (thermal throttling)
        freq = subprocess.getoutput("adb shell cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
        metrics["thermal_throttle_freq_mhz"] = int(freq) / 1000 if freq else None

        return metrics

    def parse_llama_output(self, text):
        """Extract TTFT, prefill, decode, TPS from llama.cpp logs."""
        # TPS
        tps = re.search(r"(\d+\.\d+)\s+tokens/s", text)
        tps = float(tps.group(1)) if tps else None

        # Prefill & decode
        pre = re.search(r"prefill time:\s+(\d+)", text)
        dec = re.search(r"decode time:\s+(\d+)", text)

        prefill = float(pre.group(1)) if pre else None
        decode = float(dec.group(1)) if dec else None

        # TTFT (approx: prefill time)
        ttft = prefill

        return tps, prefill, decode, ttft

    # ============================
    # SAVE RESULTS
    # ============================

    def populate_run_data(self, context: RunnerContext) -> Optional[Dict[str, Any]]:
        text = context.experiment_data["raw_output"]
        start = context.experiment_data["start_global"]
        end = context.experiment_data["end_global"]

        # system metrics
        sys_metrics = self.get_system_metrics()

        # llama-specific metrics
        tps, prefill, decode, ttft = self.parse_llama_output(text)

        # Latency
        total_latency = (end - start) * 1000

        # Energy estimation
        cur = sys_metrics["battery_current_ma"] / 1000  # to A
        volt = sys_metrics["battery_voltage_v"]
        duration = (end - start)
        joules = cur * volt * duration

        energy_per_token = joules / max(1, tps) if tps else None

        return {
            "model_load_ms": prefill,     # rough proxy from llama logs
            "ttft_ms": ttft,
            "prefill_ms": prefill,
            "decode_ms": decode,
            "tps": tps,
            "total_latency_ms": total_latency,
            **sys_metrics,
            "energy_joules": joules,
            "energy_per_token": energy_per_token,
        }

    def after_experiment(self):
        output.console_log("✔ All experiments finished!")
