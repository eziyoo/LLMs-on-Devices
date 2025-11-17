#############################################
#  COMPLETE EXPERIMENT RUNNER CONFIG
#  WITH FULL PERFORMANCE + MEMORY + ENERGY METRICS
#  LOCAL DATASETS + HF MODELS + ANDROID ADB METRICS
#############################################

from EventManager.Models.RunnerEvents import RunnerEvents
from EventManager.EventSubscriptionController import EventSubscriptionController
from ConfigValidator.Config.Models.RunTableModel import RunTableModel
from ConfigValidator.Config.Models.FactorModel import FactorModel
from ConfigValidator.Config.Models.RunnerContext import RunnerContext
from ConfigValidator.Config.Models.OperationType import OperationType
from ExtendedTyping.Typing import SupportsStr
from ProgressManager.Output.OutputProcedure import OutputProcedure as output

import torch
import psutil
import subprocess
import json
import time
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    AutoModelForCausalLM,
    AutoModelForQuestionAnswering,
    AutoModelForSequenceClassification,
)
from typing import Dict, Optional
from pathlib import Path
from os.path import dirname, realpath

##########################################################
#                    RunnerConfig
##########################################################
class RunnerConfig:
    ROOT_DIR = Path(dirname(realpath(__file__)))
    DATA_ROOT = ROOT_DIR / "datasets"

    # ================================================================
    #          EXPERIMENT CONFIGURATION
    # ================================================================
    name: str = "LLM_Full_Metrics"
    results_output_path: Path = ROOT_DIR / "experiments"
    operation_type: OperationType = OperationType.AUTO
    time_between_runs_in_ms = 20000

    # Cached model/tokenizer for speed
    _model = None
    _tokenizer = None
    _current_model_name = None

    def __init__(self):
        EventSubscriptionController.subscribe_to_multiple_events([
            (RunnerEvents.BEFORE_EXPERIMENT, self.before_experiment),
            (RunnerEvents.BEFORE_RUN,        self.before_run),
            (RunnerEvents.START_RUN,         self.start_run),
            (RunnerEvents.START_MEASUREMENT, self.start_measurement),
            (RunnerEvents.INTERACT,          self.interact),
            (RunnerEvents.STOP_MEASUREMENT,  self.stop_measurement),
            (RunnerEvents.STOP_RUN,          self.stop_run),
            (RunnerEvents.POPULATE_RUN_DATA, self.populate_run_data),
            (RunnerEvents.AFTER_EXPERIMENT,  self.after_experiment),
        ])
        self.run_table_model = None
        output.console_log("Loaded Full LLM Experiment Runner Configuration.")

    # ================================================================
    #        DEFINE RUN TABLE MODEL (TASK × MODEL)
    # ================================================================
    def create_run_table_model(self) -> RunTableModel:

        model_factor = FactorModel(
            "Model", [
            "qwen2-0_5b-instruct-q4_k_m.gguf",
            "qwen2.5-1.5b-instruct-q4_k_m.gguf",
            "phi-2.Q4_K_M.gguf",
            "qwen2.5-3b-instruct-q4_k_m.gguf",
            "OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf",
            "qwen2.5-7b-instruct-q4_k_m.gguf",
            "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
            "gemma-2-9b-it-Q4_K_M.gguf",
        ])

        task_factor = FactorModel("task", [
            "text_generation",
            "question_answering",
            "text_classification",
            "summarization",
            "translation"
        ])

        self.run_table_model = RunTableModel(
            factors=[task_factor, model_factor],
            repetitions=1,
            data_columns=[
                # Performance
                "model_load_time_ms",
                "prefill_latency_ms",
                "ttft_ms",
                "generation_latency_ms",
                "total_latency_ms",
                "tps",

                # CPU & RAM
                "cpu_percent",
                "peak_ram_mb",
                "ram_timeline_json",

                # Android metrics
                "battery_before",
                "battery_after",
                "battery_delta",
                "temp_before_c",
                "temp_after_c",
                "temp_delta_c",
                "current_ma",
                "cpu_freq_min",
                "cpu_freq_avg",
                "cpu_freq_max",
            ]
        )
        return self.run_table_model

    # ================================================================
    #             LOCAL DATASET LOADER (PER TASK)
    # ================================================================
    def load_local_dataset(self, task: str):
        path = self.DATA_ROOT

        if task == "text_generation":
            file = path / "text_generation" / "wikitext_test.txt"
            text = file.read_text().strip().split("\n")[0]
            return {"text": text}

        elif task == "question_answering":
            file = path / "question_answering" / "squad.json"
            data = json.loads(file.read_text())
            sample = data["validation"][0]
            return {"context": sample["context"], "question": sample["question"]}

        elif task == "text_classification":
            file = path / "text_classification" / "sst2.json"
            data = json.loads(file.read_text())
            sample = data["validation"][0]
            return {"text": sample["sentence"]}

        elif task == "summarization":
            file = path / "summarization" / "cnn_dm.json"
            data = json.loads(file.read_text())
            sample = data["test"][0]
            return {"article": sample["article"]}

        elif task == "translation":
            file = path / "translation" / "wmt19.json"
            data = json.loads(file.read_text())
            sample = data["train"][0]
            return {"en": sample["en"]}

        else:
            raise ValueError(f"Unknown task: {task}")

    # ================================================================
    #       ANDROID BATTERY / TEMPERATURE / THERMAL METRICS
    # ================================================================
    def adb_battery_level(self) -> Optional[int]:
        try:
            raw = subprocess.getoutput("adb shell dumpsys battery | grep level")
            return int(raw.split(":")[-1].strip())
        except Exception:
            return None

    def adb_temperature(self) -> Optional[float]:
        try:
            raw = subprocess.getoutput("adb shell dumpsys battery | grep temperature")
            return int(raw.split(":")[-1].strip()) / 10
        except Exception:
            return None

    def adb_current_ma(self) -> Optional[float]:
        try:
            raw = subprocess.getoutput("adb shell cat /sys/class/power_supply/battery/current_now")
            return abs(int(raw.strip())) / 1000  # µA → mA
        except Exception:
            return None

    def adb_cpu_freqs(self) -> Dict[str, float]:
        try:
            out = subprocess.getoutput("adb shell 'cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_cur_freq'")
            freqs = [int(x) for x in out.split() if x.isdigit()]
            if not freqs:
                return {"min": 0, "avg": 0, "max": 0}
            return {
                "min": min(freqs),
                "max": max(freqs),
                "avg": sum(freqs) / len(freqs)
            }
        except Exception:
            return {"min": 0, "avg": 0, "max": 0}

    # ================================================================
    #                 BEFORE / START HOOKS
    # ================================================================
    def before_experiment(self):
        output.console_log("Preparing experiment environment...")

    def before_run(self):
        output.console_log("Setting up for next run...")

    def start_run(self, context):
        run = context.current_run
        model_name = run["model"]
        output.console_log(f"Loading model: {model_name}")

        load_start = time.time()

        if (self._model is None) or (self._current_model_name != model_name):
            self._tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._model = None
            # Load model safely depending on architecture
            for cls in [AutoModelForSeq2SeqLM, AutoModelForCausalLM,
                        AutoModelForQuestionAnswering, AutoModelForSequenceClassification]:
                try:
                    self._model = cls.from_pretrained(model_name)
                    break
                except Exception:
                    continue
            if self._model is None:
                raise RuntimeError(f"Failed to load model {model_name}")
            self._model.eval()
            self._current_model_name = model_name

        load_end = time.time()
        context.experiment_data["model_load_time_ms"] = (load_end - load_start) * 1000

        # Android battery readings
        context.experiment_data["battery_before"] = self.adb_battery_level()
        context.experiment_data["temp_before_c"] = self.adb_temperature()

    def start_measurement(self, context):
        context.experiment_data["cpu_start"] = psutil.cpu_percent(interval=None)
        output.console_log("Measurement started.")

    # ================================================================
    #                   MAIN INFERENCE LOGIC
    # ================================================================
    def interact(self, context):
        run = context.current_run
        task = run["task"]

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model = self._model.to(device)
        tokenizer = self._tokenizer
        sample = self.load_local_dataset(task)

        mem_timeline = {"after_load_mb": psutil.Process().memory_info().rss / 1024**2}

        # ------------------------ PREFILL ------------------------
        t_pre_start = time.time()
        if task == "question_answering":
            inputs = tokenizer(sample["question"], sample["context"], return_tensors="pt", truncation=True).to(device)
        elif task == "text_classification":
            inputs = tokenizer(sample["text"], return_tensors="pt", truncation=True).to(device)
        elif task == "summarization":
            inputs = tokenizer(sample["article"], return_tensors="pt", truncation=True).to(device)
        elif task == "translation":
            inputs = tokenizer(sample["en"], return_tensors="pt", truncation=True).to(device)
        else:
            inputs = tokenizer(sample["text"], return_tensors="pt", truncation=True).to(device)
        with torch.no_grad():
            _ = model(**inputs)
        t_pre_end = time.time()
        prefill_latency = t_pre_end - t_pre_start
        context.experiment_data["prefill_latency_ms"] = prefill_latency * 1000
        mem_timeline["after_prefill_mb"] = psutil.Process().memory_info().rss / 1024**2

        # ------------------------ GENERATION ------------------------
        t_gen_start = time.time()
        try:
            outputs = model.generate(**inputs, max_new_tokens=64)
            decoded = tokenizer.decode(outputs[0], skip_special_tokens=True)
            num_tokens = outputs.shape[-1]
        except Exception:
            outputs = model(**inputs)
            decoded = str(torch.argmax(outputs.logits, dim=-1).item())
            num_tokens = 1
        t_gen_end = time.time()

        generation_latency = t_gen_end - t_gen_start
        context.experiment_data["generation_latency_ms"] = generation_latency * 1000
        context.experiment_data["total_latency_ms"] = (t_gen_end - t_pre_start) * 1000
        context.experiment_data["ttft_ms"] = (
            context.experiment_data["model_load_time_ms"] +
            context.experiment_data["prefill_latency_ms"]
        )
        context.experiment_data["tps"] = num_tokens / max(generation_latency, 1e-6)

        mem_timeline["after_generation_mb"] = psutil.Process().memory_info().rss / 1024**2
        context.experiment_data["peak_ram_mb"] = max(mem_timeline.values())
        context.experiment_data["ram_timeline_json"] = json.dumps(mem_timeline)

        # Save output text
        (context.run_dir / "raw_output.txt").write_text(decoded)

    # ================================================================
    #      POST-MEASUREMENT: BATTERY, THERMALS, CPU FREQ
    # ================================================================
    def stop_measurement(self, context):
        context.experiment_data["cpu_percent"] = psutil.cpu_percent(interval=None)
        battery_after = self.adb_battery_level()
        temp_after = self.adb_temperature()
        cpu_freqs = self.adb_cpu_freqs()
        context.experiment_data["battery_after"] = battery_after
        context.experiment_data["battery_delta"] = (
            battery_after - context.experiment_data.get("battery_before", 0)
            if battery_after is not None else None
        )
        context.experiment_data["temp_after_c"] = temp_after
        context.experiment_data["temp_delta_c"] = (
            temp_after - context.experiment_data.get("temp_before_c", 0)
            if temp_after is not None else None
        )
        context.experiment_data["current_ma"] = self.adb_current_ma()
        context.experiment_data["cpu_freq_min"] = cpu_freqs["min"]
        context.experiment_data["cpu_freq_avg"] = cpu_freqs["avg"]
        context.experiment_data["cpu_freq_max"] = cpu_freqs["max"]

    def stop_run(self, context):
        output.console_log("Run complete. Cooling down for stability...")

    # ================================================================
    #                   WRITE RESULTS TO TABLE
    # ================================================================
    def populate_run_data(self, context) -> Optional[Dict[str, SupportsStr]]:
        d = context.experiment_data
        return {
            "model_load_time_ms":   round(d.get("model_load_time_ms", 0), 3),
            "prefill_latency_ms":   round(d.get("prefill_latency_ms", 0), 3),
            "ttft_ms":              round(d.get("ttft_ms", 0), 3),
            "generation_latency_ms":round(d.get("generation_latency_ms", 0), 3),
            "total_latency_ms":     round(d.get("total_latency_ms", 0), 3),
            "tps":                  round(d.get("tps", 0), 3),
            "cpu_percent":          round(d.get("cpu_percent", 0), 2),
            "peak_ram_mb":          round(d.get("peak_ram_mb", 0), 2),
            "ram_timeline_json":    d.get("ram_timeline_json", "{}"),
            "battery_before":       d.get("battery_before"),
            "battery_after":        d.get("battery_after"),
            "battery_delta":        d.get("battery_delta"),
            "temp_before_c":        d.get("temp_before_c"),
            "temp_after_c":         d.get("temp_after_c"),
            "temp_delta_c":         d.get("temp_delta_c"),
            "current_ma":           d.get("current_ma"),
            "cpu_freq_min":         d.get("cpu_freq_min"),
            "cpu_freq_avg":         round(d.get("cpu_freq_avg", 0), 2),
            "cpu_freq_max":         d.get("cpu_freq_max"),
        }

    # ================================================================
    #                     AFTER EXPERIMENT
    # ================================================================
    def after_experiment(self):
        output.console_log("Experiment fully complete! All metrics collected.")

    experiment_path: Path = None
