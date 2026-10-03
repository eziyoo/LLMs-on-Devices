"""Parsers for the two per-run logs produced by RunnerConfig.py.

- llama_output.txt : verbose `llama-cli` output (timings, memory breakdown, response)
- run_logcat.txt   : logcat dump containing BatteryManager companion samples

RunnerConfig.py uses these functions during the experiment, and analysis/reparse_raw_logs.py
uses them to re-derive the published run tables from the raw logs.

Usage (parse one run folder):
    python experiment/log_parsers.py <run_dir> [--baseline-current 0.10]
"""
import json
import os
import re
import statistics

BATTERY_LINE_TAG = "BatteryMgr:DataCollectionService: stats =>"
DEFAULT_BASELINE_CURRENT_A = 0.10


def parse_llama_log_file(file_path, log=print):
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
                metrics['model_response'] = _fallback_clean_response(content)

    except FileNotFoundError:
        log(f"Error: File '{file_path}' not found.")

    return metrics


def _fallback_clean_response(full_text):
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


def parse_llama_memory(file_path, log=print):
    metrics = {
        "kv_cache_size_mb": 0.0,
        "peak_memory_mb": 0.0,
        "model_weight_mb": 0.0,
        "context_ram_mb": 0.0,
        "compute_ram_mb": 0.0
    }

    if not os.path.exists(file_path):
        log(f"Error: The file '{file_path}' was not found.")
        return metrics

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        log_content = f.read()

    # 1. Extract KV Cache Size
    # Target: "llama_kv_cache: size =    84.00 MiB"
    kv_match = re.search(r"llama_kv_cache:\s+size\s+=\s+([\d\.]+)\s+MiB", log_content)
    if kv_match:
        metrics["kv_cache_size_mb"] = float(kv_match.group(1))

    # 2. Extract Memory Breakdown
    # Target: "5612 =  4937 +     168 +     507"
    # Format: Total = Model + Context + Compute
    mem_match = re.search(r"(\d+)\s+=\s+(\d+)\s+\+\s+(\d+)\s+\+\s+(\d+)", log_content)
    if mem_match:
        metrics["peak_memory_mb"] = float(mem_match.group(1))    # Group 1: Total
        metrics["model_weight_mb"] = float(mem_match.group(2))   # Group 2: Model
        metrics["context_ram_mb"] = float(mem_match.group(3))    # Group 3: Context
        metrics["compute_ram_mb"] = float(mem_match.group(4))    # Group 4: Compute

    return metrics


def parse_battery_log(battery_log_path, output_token_count, baseline_current_a=DEFAULT_BASELINE_CURRENT_A):
    """Energy and device stats from BatteryManager samples (trapezoidal integration)."""
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
                if BATTERY_LINE_TAG in line:
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

                        # Current: µA -> Amps. Subtract the idle baseline current.
                        current_A = max(0, (abs(curr_raw) / 1000000.0) - baseline_current_a)

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

    # --- Aggregate Results ---
    avg_current = statistics.mean(currents_A) if currents_A else 0
    avg_voltage = statistics.mean(voltages_V) if voltages_V else 0
    avg_power = statistics.mean(power_readings) if power_readings else 0
    avg_capacity = statistics.mean(capacities_pct) if capacities_pct else 0
    min_battery = min(capacities_pct) if capacities_pct else 0
    max_battery = max(capacities_pct) if capacities_pct else 0
    avg_temp = statistics.mean(temps_c) if temps_c else 0
    min_temp = min(temps_c) if temps_c else 0
    max_temp = max(temps_c) if temps_c else 0

    # Energy Per Token
    energy_per_token = total_energy_joules / output_token_count if output_token_count > 0 else 0

    return {
        'avg_current': round(avg_current, 6),
        'avg_voltage': round(avg_voltage, 4),
        'avg_power': round(avg_power, 4),
        'total_energy_consumption': round(total_energy_joules, 4),
        'energy_per_token': round(energy_per_token, 4),
        'battery_capacity': round(avg_capacity, 2),
        'min_battery_capacity': round(min_battery, 2),
        'max_battery_capacity': round(max_battery, 2),
        'average_temperature': round(avg_temp, 2),
        'min_temperature': round(min_temp, 2),
        'max_temperature': round(max_temp, 2),
    }


def parse_run(run_dir, baseline_current_a=DEFAULT_BASELINE_CURRENT_A, log=print):
    """Full run-table row (all metrics) for one run folder."""
    llama_log_path = os.path.join(run_dir, "llama_output.txt")
    battery_log_path = os.path.join(run_dir, "run_logcat.txt")

    llama_metrics = {
        'model_response': '',
        'input_token_count': 0, 'output_token_count': 0, 'total_token_count': 0,
        'prompt_prefill_speed': 0.0, 'generation_decoder_speed': 0.0,
        'prefill_latency': 0.0, 'generation_latency': 0.0, 'inference_latency': 0.0,
        'time_to_first_token': 0.0
    }
    memory_metrics = {
        "kv_cache_size_mb": 0.0,
        "peak_memory_mb": 0.0,
        "model_weight_mb": 0.0,
        "context_ram_mb": 0.0,
        "compute_ram_mb": 0.0
    }

    if os.path.exists(llama_log_path):
        try:
            llama_metrics = parse_llama_log_file(llama_log_path, log=log)
            memory_metrics = parse_llama_memory(llama_log_path, log=log)
        except Exception as e:
            log(f"Error parsing llama logs: {e}")

    battery = parse_battery_log(battery_log_path, llama_metrics.get('output_token_count', 0), baseline_current_a)

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
        **battery,

        # Memory Stats
        'peak_memory': memory_metrics.get("peak_memory_mb", 0.0),
        'model_weight': memory_metrics.get("model_weight_mb", 0.0),
        'KV_cache': memory_metrics.get("kv_cache_size_mb", 0.0),
        'context_RAM': memory_metrics.get("context_ram_mb", 0.0),
        'compute_RAM': memory_metrics.get("compute_ram_mb", 0.0)
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Parse one run folder (llama_output.txt + run_logcat.txt).")
    parser.add_argument("run_dir")
    parser.add_argument("--baseline-current", type=float, default=DEFAULT_BASELINE_CURRENT_A,
                        help="idle current in A subtracted from every sample (default: %(default)s)")
    args = parser.parse_args()

    row = parse_run(args.run_dir, args.baseline_current)
    print(json.dumps(row, indent=2, ensure_ascii=False))
