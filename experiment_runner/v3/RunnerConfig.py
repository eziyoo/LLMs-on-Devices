import subprocess, time, re, json, random
import pandas as pd
from pathlib import Path
from os.path import dirname, realpath
from typing import Dict, Any, Optional, List

from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ProgressManager.Output.OutputProcedure import OutputProcedure as output



TASK_SPECS = {
    "text_generation": {
        "dataset": "wikitext_2",
        "metric": "bertscore",
        "prompt_template": "Continue the following text:\n{input}\n"
    },
    "question_answering": {
        "dataset": "SQuAD",
        "metric": "bertscore",
        "prompt_template": "Answer the question based on context:\nContext: {context}\nQuestion: {question}\nAnswer:"
    },
    "text_classification": {
        "dataset": "SST_2",
        "metric": "auc_roc",
        "prompt_template": "Classify the sentiment as positive or negative.\nText: {input}\nSentiment:"
    },
    "summarization": {
        "dataset": "CNN_DailyMail",
        "metric": "bertscore",
        "prompt_template": "Summarize the following news article:\n{input}\nSummary:"
    },
    "translation": {
        "dataset": "WMT19",
        "metric": "comet",
        "prompt_template": "Translate this English sentence into German:\n{input}\nGerman:"
    }
}


class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))
    name = "llama_android_full_experiment"
    results_output_path = ROOT_DIR / "experiments"
    operation_type = OperationType.AUTO
    time_between_runs_in_ms = 2000

    # ==========================================================
    # INITIALIZATION
    # ==========================================================
    def __init__(self):
        EventSubscriptionController.subscribe_to_multiple_events([
            (RunnerEvents.BEFORE_EXPERIMENT, self.before_experiment),
            (RunnerEvents.BEFORE_RUN, self.before_run),
            (RunnerEvents.START_RUN, self.start_run),
            (RunnerEvents.INTERACT, self.interact),
            (RunnerEvents.POPULATE_RUN_DATA, self.populate_run_data),
            (RunnerEvents.AFTER_EXPERIMENT, self.after_experiment)
        ])
        output.console_log("Loaded full RunnerConfig with parquet dataset support.")

    # ==========================================================
    # THREAD AUTODETECT
    # ==========================================================
    def get_max_threads(self):
        raw = subprocess.getoutput('adb shell "grep -c ^processor /proc/cpuinfo"')
        try:
            return int(raw.strip())
        except:
            return 4

    # ==========================================================
    # DATASET LOADER (ALWAYS PARQUET)
    # ==========================================================
    def load_parquet_samples(self, dataset_name: str, n_samples: int = 50):
        dataset_path = self.ROOT_DIR / "datasets" / dataset_name
        files = list(dataset_path.glob("*.parquet"))

        if not files:
            raise FileNotFoundError(f"No parquet file in: {dataset_path}")

        df = pd.read_parquet(files[0])

        if len(df) > n_samples:
            df = df.sample(n_samples, random_state=random.randint(1, 999999))

        return df

    # ==========================================================
    # RUN TABLE DEFINITION
    # ==========================================================
    def create_run_table_model(self) -> RunTableModel:

        model_factor = FactorModel("model", [
            "qwen2-0_5b-instruct-q4_k_m.gguf",
            "qwen2.5-1.5b-instruct-q4_k_m.gguf",
            "phi-2.Q4_K_M.gguf",
            "qwen2.5-3b-instruct-q4_k_m.gguf",
            "OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf",
            "qwen2.5-7b-instruct-q4_k_m.gguf",
            "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
            "gemma-2-9b-it-Q4_K_M.gguf"
        ])

        task_factor = FactorModel("task", list(TASK_SPECS.keys()))

        threads_factor = FactorModel("threads", [self.get_max_threads()])

        return RunTableModel(
            factors=[model_factor, task_factor, threads_factor],
            repetitions=1,
            data_columns=[
                "tps",
                "total_latency_ms",
                "ttft_ms",
                "prefill_ms",
                "decode_ms",
                "cpu_usage",
                "peak_ram_kb",
                "battery_temp_c",
                "battery_current_ma",
                "battery_voltage_v",
                "energy_joules",
                "energy_per_token",
                "thermal_throttle_freq_mhz"
            ]
        )

    # ==========================================================
    # BEFORE EXPERIMENT
    # ==========================================================
    def before_experiment(self):
        output.console_log("Pushing llama binaries and models to device…")

        subprocess.run("adb push build-android/bin/llama-cli /data/local/tmp/", shell=True)
        subprocess.run("adb push build-android/bin/lib*.so /data/local/tmp/", shell=True)
        subprocess.run("adb push models/*.gguf /data/local/tmp/models/", shell=True)
        subprocess.run("adb shell chmod +x /data/local/tmp/llama-cli", shell=True)

    # ==========================================================
    # BEFORE RUN
    # ==========================================================
    def before_run(self):
        subprocess.run("adb shell sync; adb shell echo 3 > /proc/sys/vm/drop_caches", shell=True)

    # ==========================================================
    # START RUN
    # ==========================================================
    def start_run(self, context: RunnerContext):
        output.console_log(f"Starting run: {context.current_run_name}")

    # ==========================================================
    # MAIN INFERENCE LOOP (50 SAMPLES)
    # ==========================================================
    def interact(self, context: RunnerContext):
        run = context.current_run
        model = run["model"]
        task = run["task"]
        threads = run["threads"]

        task_spec = TASK_SPECS[task]

        df = self.load_parquet_samples(task_spec["dataset"], 50)

        all_results = []

        for _, row in df.iterrows():

            # Build prompts by task
            if task == "summarization":
                input_text = row["article"]
                reference = row["highlights"]

            elif task == "translation":
                input_text = row["en"]
                reference = row["de"]

            elif task == "text_classification":
                input_text = row["sentence"]
                reference = row["label"]

            elif task == "question_answering":
                input_text = None
                context_text = row["context"]
                question = row["question"]
                reference = row["answer"]

                prompt = task_spec["prompt_template"].format(
                    context=context_text, question=question
                )

            else:  # text generation
                input_text = row["text"]
                reference = None

            if input_text is not None:
                prompt = task_spec["prompt_template"].format(input=input_text)

            # Push prompt to device
            with open("/tmp/prompt.txt", "w") as f:
                f.write(prompt)
            subprocess.run("adb push /tmp/prompt.txt /data/local/tmp/prompt.txt", shell=True)

            # Run inference
            adb_cmd = (
                f'adb shell "cd /data/local/tmp && '
                f'LD_LIBRARY_PATH=. ./llama-cli '
                f'-m models/{model} '
                f'-t {threads} '
                f'--prompt-file prompt.txt '
                f'--n-predict 128"'
            )

            start = time.time()
            raw_output = subprocess.getoutput(adb_cmd)
            end = time.time()

            all_results.append({
                "raw": raw_output,
                "duration": end - start,
                "reference": reference,
                "prompt": prompt
            })

        context.experiment_data["samples"] = all_results

    # ==========================================================
    # METRIC EXTRACTION HELPERS
    # ==========================================================
    def parse_llama_output(self, text):
        tps = re.search(r"(\d+\.\d+)\s+tokens/s", text)
        tps = float(tps.group(1)) if tps else None

        pre = re.search(r"prefill time:\s+(\d+)", text)
        dec = re.search(r"decode time:\s+(\d+)", text)

        prefill = float(pre.group(1)) if pre else None
        decode = float(dec.group(1)) if dec else None
        ttft = prefill

        return tps, prefill, decode, ttft

    def get_system_metrics(self):
        metrics = {}

        # CPU %
        cpu_raw = subprocess.getoutput('adb shell top -b -n 1 | grep llama')
        cpu_vals = re.findall(r'\s(\d+)%\s', cpu_raw)
        metrics["cpu_usage"] = int(cpu_vals[0]) if cpu_vals else None

        # RAM
        pid = subprocess.getoutput("adb shell pidof llama-cli")
        meminfo = subprocess.getoutput(f"adb shell dumpsys meminfo {pid}")
        rss = re.search(r"TOTAL:\s+(\d+)", meminfo)
        metrics["peak_ram_kb"] = int(rss.group(1)) if rss else None

        # Temp
        temp_raw = subprocess.getoutput("adb shell dumpsys battery | grep temperature")
        t = re.findall(r"(\d+)", temp_raw)
        metrics["battery_temp_c"] = float(t[0]) / 10 if t else None

        # Current (mA)
        cur = subprocess.getoutput("adb shell cat /sys/class/power_supply/battery/current_now")
        metrics["battery_current_ma"] = float(cur) / 1000 if cur else None

        # Voltage (V)
        volt = subprocess.getoutput("adb shell cat /sys/class/power_supply/battery/voltage_now")
        metrics["battery_voltage_v"] = float(volt) / 1_000_000 if volt else None

        # Thermal throttling
        freq = subprocess.getoutput("adb shell cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
        metrics["thermal_throttle_freq_mhz"] = int(freq) / 1000 if freq else None

        return metrics

    # ==========================================================
    # POPULATE RUN DATA (AGGREGATE OVER 50 SAMPLES)
    # ==========================================================
    def populate_run_data(self, context: RunnerContext) -> Optional[Dict[str, Any]]:
        samples = context.experiment_data["samples"]

        tps_values = []
        latency_values = []
        prefill_values = []
        decode_values = []
        ttft_values = []

        for sample in samples:
            raw = sample["raw"]
            duration = sample["duration"]

            tps, pre, dec, ttft = self.parse_llama_output(raw)

            if tps: tps_values.append(tps)
            if pre: prefill_values.append(pre)
            if dec: decode_values.append(dec)
            if ttft: ttft_values.append(ttft)

            latency_values.append(duration * 1000)

        # Aggregate
        mean_tps = sum(tps_values) / len(tps_values)
        mean_latency = sum(latency_values) / len(latency_values)
        mean_prefill = sum(prefill_values) / len(prefill_values)
        mean_decode = sum(decode_values) / len(decode_values)
        mean_ttft = sum(ttft_values) / len(ttft_values)

        # System metrics (single snapshot)
        sys_metrics = self.get_system_metrics()

        # Energy calculation
        current_a = sys_metrics["battery_current_ma"] / 1000
        voltage_v = sys_metrics["battery_voltage_v"]
        total_s = mean_latency / 1000

        joules = current_a * voltage_v * total_s
        energy_per_token = joules / max(mean_tps, 1)

        return {
            "tps": mean_tps,
            "total_latency_ms": mean_latency,
            "ttft_ms": mean_ttft,
            "prefill_ms": mean_prefill,
            "decode_ms": mean_decode,
            **sys_metrics,
            "energy_joules": joules,
            "energy_per_token": energy_per_token
        }

    # ==========================================================
    # AFTER EXPERIMENT
    # ==========================================================
    def after_experiment(self):
        output.console_log("All experiments complete.")
