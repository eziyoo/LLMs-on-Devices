# Reproducing the Experiment

This guide takes you from an empty machine to the per-run measurements, aggregated results, quality scores and statistical tests reported in *"Sustainability Is Not Linear: Quantifying Performance, Energy, and Privacy Trade-offs in On-Device Intelligence"*.

It assumes basic familiarity with Python, a terminal and Android developer options. No rooting and no hardware modification are needed.

---

## Published data (no phone needed)

The repository contains everything measured for the paper, so you can re-run the analysis without repeating the experiment:

| Path | Content |
|---|---|
| `experiment_runner/csv/1_…_Q4_K_M.csv` … `16_…_IQ4_XS.csv` | Final per-run tables: 16 configurations × 30 runs, all metrics plus the model response |
| `data/raw_logs_ER2.zip` | Raw per-run logs behind those tables (see [`data/README.md`](../data/README.md)) |
| `experiment_runner/Results/final_results.xlsx` | Aggregated medians (IQR) + quality scores, the input of `EDA.ipynb` |
| `experiment_runner/quality_metrics/results/` | `BERTscore.csv` and `llm_a_judge_scores.csv` |
| `experiment_runner/statistics/` | The statistical tests reported in the paper, with their input tables |

To reproduce the paper's tables and figures, install `requirements.txt` (section 4) and go to [section 14](#14-aggregate-results-and-plot).

---

## Contents

1. [Overview and time budget](#1-overview-and-time-budget)
2. [Requirements](#2-requirements)
3. [Repository layout](#3-repository-layout)
4. [Host setup](#4-host-setup)
5. [Build llama.cpp for Android](#5-build-llamacpp-for-android)
6. [Prepare the models](#6-prepare-the-models)
7. [Prepare the phone](#7-prepare-the-phone)
8. [Install the BatteryManager companion app](#8-install-the-batterymanager-companion-app)
9. [Connect over wireless ADB](#9-connect-over-wireless-adb)
10. [Sanity check on the device](#10-sanity-check-on-the-device)
11. [Measure the idle baseline](#11-measure-the-idle-baseline)
12. [Configure `RunnerConfig.py`](#12-configure-runnerconfigpy)
13. [Run the experiment](#13-run-the-experiment)
14. [Aggregate results and plot](#14-aggregate-results-and-plot)
15. [Evaluate output quality](#15-evaluate-output-quality)
16. [Statistical analysis](#16-statistical-analysis)
17. [Troubleshooting](#17-troubleshooting)
18. [Appendix](#18-appendix)

---

## 1. Overview and time budget

```
 Host (laptop)                                   Android phone (unrooted)
 ┌──────────────────────────┐   wireless ADB    ┌────────────────────────────────┐
 │ Experiment-Runner        │ ───────────────►  │ /data/local/tmp/llama-cli      │
 │  └ experiment_runner/    │                   │ /data/local/tmp/*.gguf         │
 │     RunnerConfig.py      │ ◄───────────────  │ BatteryManager companion app   │
 │ parsers → run_table.csv  │  logs (pull)      │  (current, voltage, temp @100ms│
 └──────────────────────────┘                   │   → logcat)                    │
                                                └────────────────────────────────┘
```

For every run, `RunnerConfig.py` does the following:

1. Clears logcat.
2. Starts the on-device battery logger (100 ms sampling) and waits 2 s for it to spin up.
3. Runs `llama-cli` with a fixed summarization prompt.
4. Stops the logger and pulls the llama log and the logcat dump to the host.
5. Parses latency, throughput, memory and energy into one row of `run_table.csv`.
6. Waits 200 s to cool down.

**Design:** 8 models × 2 quantizations (`Q4_K_M`, `IQ4_XS`) = 16 configurations, 30 repetitions each.

**Time:** one run takes about 3.5 to 4 minutes, mostly the 200 s cool-down. That is about 2 hours per configuration, or **about 32 hours** for all 16. The paper ran one configuration per testing round and recharged the phone between rounds.

---

## 2. Requirements

### Hardware

| Item | Requirement | Used in the paper |
|---|---|---|
| Phone | Android, arm64, **≥12 GB RAM** (needed for the 7–9B models). Android 13+ recommended. | Samsung Galaxy S25 Ultra, Snapdragon 8 Elite, 12 GB, Android 16 |
| Host | macOS, Linux, or Windows with WSL2 | MacBook Air M4 |
| Network | A **third device** acting as a Wi-Fi hotspot that both the host and the phone join | A spare phone as hotspot |
| USB cable | Only for setup and pushing models. It must be **unplugged** during measurements. | |

Do not use the target phone's own hotspot, because it adds radio power draw. University and public Wi-Fi networks usually block ADB.

### Software (host)

| Tool | Version / note |
|---|---|
| Python | 3.10+ |
| `git`, `cmake` (≥3.22), a C/C++ compiler | To build llama.cpp |
| Android SDK Platform-Tools (`adb`) | Must be on `PATH` |
| Android NDK | r29 was used; any recent NDK should work |
| Jupyter | For the aggregation and plotting notebooks (installed by `requirements.txt`) |
| Hugging Face account | Llama 3.1 and Gemma 2 are gated, so accept their licenses first |
| OpenAI API key | Only for the LLM-as-a-judge step |

### Disk space

- Host: about 60 GB (FP16 conversions are deleted after quantizing).
- Phone: enough free internal storage for the models of the current round. The largest pair (Gemma-2-9B) is about 11 GB.

---

## 3. Repository layout

```
LLMs-on-Devices/
├── experiment_runner/
│   ├── RunnerConfig.py            # The pipeline (Experiment-Runner config)
│   ├── parser/                    # Standalone copies of the log parsers, for debugging
│   ├── quality_metrics/
│   │   ├── BERTscore.py           # Reference-based quality
│   │   ├── test_DeepEval.py       # LLM-as-a-judge (G-Eval style)
│   │   └── results/               # Published quality scores
│   ├── quantization/              # imatrix + IQ4_XS quantization notebook
│   ├── csv/                       # Per-configuration run tables (published data)
│   ├── csv_processor.ipynb        # Per-run CSVs → medians + IQR
│   ├── Results/                   # EDA.ipynb (plots) + final_results.xlsx
│   └── statistics/                # Shapiro-Wilk, Wilcoxon, Friedman + Holm scripts
├── data/raw_logs_ER2.zip          # Raw per-run logs of the final run
├── plugins/BatteryManager/spy_app/  # Companion APK (on-device energy logger)
├── plugins/perfetto/              # Earlier CPU-frequency power-model prototype (not used)
├── scrapers/                      # HF GGUF model list + dataset downloader
├── android-app/                   # Early chat/bench app prototype (not used)
├── docs/REPRODUCE.md              # This guide
└── requirements.txt
```

---

## 4. Host setup

Pick a working folder, for example `~/llm_on_device`, and clone three repositories into it:

```bash
mkdir -p ~/llm_on_device && cd ~/llm_on_device

git clone https://github.com/eziyoo/LLMs-on-Devices.git
git clone https://github.com/S2-group/experiment-runner.git
git clone https://github.com/ggml-org/llama.cpp.git

python3 -m venv venv
source venv/bin/activate

pip install -r LLMs-on-Devices/requirements.txt
pip install -r experiment-runner/requirements.txt
```

Check that `adb` works:

```bash
adb version
```

---

## 5. Build llama.cpp for Android

### 5.1 Cross-compile `llama-cli`

```bash
cd ~/llm_on_device/llama.cpp
export ANDROID_NDK=/path/to/android-ndk-r29        # adjust

cmake -B build-android \
  -DCMAKE_TOOLCHAIN_FILE=$ANDROID_NDK/build/cmake/android.toolchain.cmake \
  -DANDROID_ABI=arm64-v8a \
  -DANDROID_PLATFORM=android-28 \
  -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=ON \
  -DLLAMA_CURL=OFF

cmake --build build-android --config Release -j
```

You should now have `build-android/bin/llama-cli` and several `lib*.so` files next to it.

### 5.2 Add the OpenMP runtime

`llama-cli` links against `libomp.so`, which is not on the phone. Copy it from the NDK into the build folder. `RunnerConfig.py` pushes every `lib*.so` in that folder automatically.

```bash
cp "$(find $ANDROID_NDK -path '*linux/aarch64/libomp.so' | head -n1)" build-android/bin/
```

### 5.3 Record the version

```bash
git rev-parse HEAD > build-android/LLAMA_COMMIT.txt
```

The parsers in `RunnerConfig.py` rely on llama.cpp's verbose output format. If you use a much newer or older commit, run the [sanity check](#10-sanity-check-on-the-device) first.

### 5.4 Host build (for quantizing)

To quantize models yourself (section 6), also build llama.cpp for the host:

```bash
cmake -B build && cmake --build build --config Release -j
```

---

## 6. Prepare the models

`RunnerConfig.py` expects these **exact filenames**:

| # | Base model (Hugging Face) | `Q4_K_M` file | `IQ4_XS` file |
|---|---|---|---|
| 1 | `Qwen/Qwen2-0.5B-Instruct` | `qwen2-0_5b-instruct-q4_k_m.gguf` | `Qwen2-0.5b-instruct-iq4_xs.gguf` |
| 2 | `Qwen/Qwen2.5-1.5B-Instruct` | `qwen2.5-1.5b-instruct-q4_k_m.gguf` | `Qwen2.5-1.5B-Instruct-IQ4_XS.gguf` |
| 3 | `microsoft/phi-2` | `phi-2.Q4_K_M.gguf` | `Phi-2-iq4_xs.gguf` |
| 4 | `Qwen/Qwen2.5-3B-Instruct` | `qwen2.5-3b-instruct-q4_k_m.gguf` | `Qwen2.5-3B-Instruct-IQ4_XS.gguf` |
| 5 | `allenai/OLMoE-1B-7B-0125-Instruct` | `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` | `OLMoE-1B-7B-0125-Instruct-i1-IQ4_XS.gguf` |
| 6 | `Qwen/Qwen2.5-7B-Instruct` | `qwen2.5-7b-instruct-q4_k_m.gguf` | `Qwen2.5-7B-Instruct-IQ4_XS.gguf` |
| 7 | `meta-llama/Llama-3.1-8B-Instruct` (gated) | `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` | `Meta-Llama-3.1-8B-Instruct-IQ4_XS.gguf` |
| 8 | `google/gemma-2-9b-it` (gated) | `gemma-2-9b-it-Q4_K_M.gguf` | `gemma-2-9b-it-IQ4_XS.gguf` |

> **The filename selects the prompt template.** `RunnerConfig.interact()` picks the chat template by substring of the lower-cased filename: `gemma`, `phi-2`, `llama-3` or `olmoe`, and Qwen ChatML for everything else. If you rename files, keep these substrings.

### Option A: quantize yourself (fully reproducible)

```bash
cd ~/llm_on_device
huggingface-cli login
huggingface-cli download Qwen/Qwen2.5-3B-Instruct --local-dir hf/Qwen2.5-3B-Instruct

# 1. Convert to FP16 GGUF
python llama.cpp/convert_hf_to_gguf.py hf/Qwen2.5-3B-Instruct \
  --outfile f16/qwen2.5-3b-f16.gguf --outtype f16

# 2. Q4_K_M
llama.cpp/build/bin/llama-quantize f16/qwen2.5-3b-f16.gguf \
  models/qwen2.5-3b-instruct-q4_k_m.gguf Q4_K_M

# 3. IQ4_XS (needs an importance matrix computed on calibration text, e.g. WikiText-2 train)
llama.cpp/build/bin/llama-imatrix -m f16/qwen2.5-3b-f16.gguf -f wiki.train.raw -o imatrix.dat
llama.cpp/build/bin/llama-quantize --imatrix imatrix.dat f16/qwen2.5-3b-f16.gguf \
  models/Qwen2.5-3B-Instruct-IQ4_XS.gguf IQ4_XS
```

[`experiment_runner/quantization/phi-2_imatrix_quantization.ipynb`](../experiment_runner/quantization/phi-2_imatrix_quantization.ipynb) shows the same IQ4_XS flow end to end. It runs on a Kaggle GPU and downloads WikiText-2 as calibration data.

### Option B: pre-quantized GGUFs

Many of these models are published as GGUF on Hugging Face, either by the original authors or by community quantizers. Download the matching quantization and rename it to the filename in the table. Quantizations from different sources can use different imatrix calibration data, so Option A is preferred for exact replication.

---

## 7. Prepare the phone

1. **Developer options:** go to *Settings → About phone → Software information* and tap *Build number* 7 times.
2. **Enable** *USB debugging* and *Wireless debugging* in *Developer options*.
3. **Isolate background activity** so it doesn't add noise to the energy readings:
   - Turn off auto-sync, automatic app and system updates, Bluetooth, NFC, location and mobile data.
   - Turn on *Do Not Disturb*.
   - Close all apps.
4. **Display:** set brightness to the minimum and turn off adaptive brightness. `RunnerConfig.py` keeps the screen on (it sets `screen_off_timeout` to the maximum and restores 2 minutes at the end).
   - Optional, via adb:
     ```bash
     adb shell settings put system screen_brightness_mode 0
     adb shell settings put system screen_brightness 1
     ```
5. **Battery:** charge to 100 %, then unplug. Keep the battery between **80 % and 100 %** during a round, and recharge between rounds.
6. **Thermals:** remove the case, lay the phone flat on a table, keep it at stable room temperature and out of direct sun.

---

## 8. Install the BatteryManager companion app

The companion app ([S2-group/batterymanager-companion](https://github.com/S2-group/batterymanager-companion)) runs on the phone. It reads current, voltage, capacity and temperature through the Android `BatteryManager` API, which needs no root, and prints one line per sample to logcat.

With the phone connected over USB:

```bash
cd ~/llm_on_device/LLMs-on-Devices
adb install -g plugins/BatteryManager/spy_app/com.example.batterymanager_utility.apk

adb shell pm grant com.example.batterymanager_utility android.permission.POST_NOTIFICATIONS
adb shell dumpsys deviceidle whitelist +com.example.batterymanager_utility
```

The whitelist step stops Samsung's battery optimizer from killing the service.

**Smoke test (10 s):**

```bash
adb shell logcat -c
adb shell am start-foreground-service \
  -n "com.example.batterymanager_utility/com.example.batterymanager_utility.DataCollectionService" \
  --ei sampleRate 100 \
  --es "dataFields" "BATTERY_PROPERTY_CURRENT_NOW,EXTRA_VOLTAGE,BATTERY_PROPERTY_CAPACITY,EXTRA_TEMPERATURE" \
  --ez toCSV False
sleep 10
adb shell am stopservice com.example.batterymanager_utility/com.example.batterymanager_utility.DataCollectionService
adb shell logcat -d | grep "BatteryMgr:DataCollectionService: stats =>" | head
```

Expect lines like `... stats => 1738000000000,-412345,4381,97,268`, which are the timestamp (ms), current (µA), voltage (mV), capacity (%) and temperature (tenths of °C).

`toCSV False` is intentional. Samples go to logcat instead of being buffered in the app's RAM, which would compete with the LLM for memory.

To rebuild the app from source, use the patched fork: [`eziyoo/batterymanager-companion`, branch `fix-battery-property-crash`](https://github.com/eziyoo/batterymanager-companion/tree/fix-battery-property-crash). Upstream code without the fix crashes; see [Appendix A](#a-batterymanager-crash-fix).

---

## 9. Connect over wireless ADB

USB must be disconnected during measurement, because the host would charge the phone and corrupt discharge-based energy readings.

1. Turn on the hotspot on the **third device** and connect both the host and the phone to it.
2. **Push the models now, over USB**, because pushing several GB over Wi-Fi is slow. `RunnerConfig.py` skips files that already exist on the device.
   ```bash
   adb push models/<model>.gguf /data/local/tmp/
   ```
3. Switch ADB to TCP and connect:
   ```bash
   adb tcpip 5555
   # unplug the USB cable now
   adb connect <PHONE_IP>:5555     # IP: Settings → About phone → Status → IP address
   adb devices                     # should list <PHONE_IP>:5555  device
   ```

   On Android 11+ you can instead pair through *Wireless debugging → Pair device with pairing code* (`adb pair <ip>:<port>`, then `adb connect`).

**WSL2 users:** attach the USB device to WSL first (`usbipd attach --wsl --busid <id>` in PowerShell). For the wireless step, `adb connect` must reach the phone's IP from inside WSL.

`<PHONE_IP>:5555` is your `DEVICE_ID` in section 12.

---

## 10. Sanity check on the device

Run one generation by hand. If the binary was not pushed yet, push it first with `adb push ~/llm_on_device/llama.cpp/build-android/bin/* /data/local/tmp/`.

```bash
adb -s <PHONE_IP>:5555 shell "chmod +x /data/local/tmp/llama-cli && cd /data/local/tmp && \
  LD_LIBRARY_PATH=. ./llama-cli -m qwen2-0_5b-instruct-q4_k_m.gguf \
  -p 'Summarize: The World Wide Web was invented in 1989 at CERN.' \
  -st -v -n 32 -c 512 -t 8 --temp 0 > /data/local/tmp/check.txt 2>&1"
adb -s <PHONE_IP>:5555 pull /data/local/tmp/check.txt .
grep -E "prompt eval time|eval time|total time|Parsed message|llama_kv_cache|[0-9]+ = +[0-9]+ \+" check.txt
```

The parsers need all of these lines in the output:

| Line | Gives |
|---|---|
| `prompt eval time = … ms / N tokens (… tokens per second)` | prefill latency, input tokens, prefill speed |
| `eval time = … ms / N runs (… ms per token, … tokens per second)` | generation latency, output tokens, decode speed, TTFT |
| `total time = … ms` | end-to-end latency |
| `Parsed message: {...}` | the model's response text |
| `llama_kv_cache: size = … MiB` and `<total> = <model> + <context> + <compute>` | memory breakdown |

If any line is missing, your llama.cpp version prints a different format. Use a commit closer to the one recorded for the paper, or adjust the regexes in `RunnerConfig._parse_llama_log_file` and `_parse_llama_memory`. The standalone copies in `experiment_runner/parser/` are handy for testing.

---

## 11. Measure the idle baseline

Energy is reported **net of idle draw**: each current sample has the phone's idle current subtracted. Measure the idle current on your own device, under the same conditions as the runs: screen on, minimum brightness, no foreground workload, wireless ADB connected.

```bash
adb shell logcat -G 16M          # enlarge the log buffer so a long recording isn't overwritten
adb shell logcat -c
adb shell am start-foreground-service \
  -n "com.example.batterymanager_utility/com.example.batterymanager_utility.DataCollectionService" \
  --ei sampleRate 1000 \
  --es "dataFields" "BATTERY_PROPERTY_CURRENT_NOW,EXTRA_VOLTAGE,BATTERY_PROPERTY_CAPACITY,EXTRA_TEMPERATURE" \
  --ez toCSV False

# leave the phone untouched for at least 1 hour (the paper used 2 hours)

adb shell am stopservice com.example.batterymanager_utility/com.example.batterymanager_utility.DataCollectionService
adb shell logcat -d | grep "BatteryMgr:DataCollectionService: stats =>" > baseline_logcat.txt
```

The baseline uses a 1 s sample rate so the log stays small. The mean is unaffected by the sample rate.

Compute the mean:

```bash
python - <<'EOF'
import statistics
amps, watts = [], []
for line in open("baseline_logcat.txt"):
    p = line.split("stats => ")[1].strip().split(",")
    a, v = abs(int(p[1])) / 1e6, int(p[2]) / 1000
    amps.append(a); watts.append(a * v)
print(f"samples={len(amps)}  mean_current={statistics.mean(amps):.4f} A  mean_power={statistics.mean(watts):.4f} W")
EOF
```

Put `mean_current` into `RunnerConfig.populate_run_data`, replacing the `0.10` in:

```python
current_A = max(0, (abs(curr_raw) / 1000000.0) - 0.10)
```

---

## 12. Configure `RunnerConfig.py`

Open [`experiment_runner/RunnerConfig.py`](../experiment_runner/RunnerConfig.py) and edit these constants. **Run one configuration per round.**

| Setting | Where | Set to |
|---|---|---|
| `name` | class attribute | A unique name per round that matches the CSV naming in section 13, e.g. `"1_qwen2-0_5b_Q4_K_M"` |
| `DEVICE_ID` | class attribute | `<PHONE_IP>:5555` (exactly as shown by `adb devices`) |
| `LOCAL_LLAMA_BUILD` | class attribute | `~/llm_on_device/llama.cpp/build-android/bin` |
| `LOCAL_MODEL_PATH` | class attribute | Path to **the single `.gguf` file** for this round. A folder also works, but every `.gguf` in it is pushed. |
| Factor list | `create_run_table_model()` | Uncomment **exactly one** filename, the model for this round |
| `repetitions` | `create_run_table_model()` | `30` |
| `WARMUP_MODEL` | `before_experiment()` | The same filename as the model under test. It defaults to `gemma-2-9b-it-IQ4_XS.gguf`, which must otherwise be on the device. |
| `time_between_runs_in_ms` | class attribute | `200000` (200 s cool-down) |
| Baseline current | `populate_run_data()` | Your value from section 11 |

These fixed inference settings stay as they are, so results are comparable to the paper:

- `-n 100 --ignore-eos`, with the model's end-of-turn token banned through `--logit-bias <id>-inf`, so every run generates exactly 100 tokens.
- `-c 512 -t 8 --temp 0` (deterministic greedy decoding, 8 threads).
- The same summarization text for every model, wrapped in each model's chat template.

---

## 13. Run the experiment

Before each round, check that:

- The phone is between 80 % and 100 % charged and **unplugged**.
- `adb devices` shows the wireless device.
- The screen is on at minimum brightness.

Then start the round:

```bash
cd ~/llm_on_device/LLMs-on-Devices
source ../venv/bin/activate
python ../experiment-runner/experiment-runner/ experiment_runner/RunnerConfig.py
```

What happens:

1. **Setup:** clears logcat, keeps the screen on, pushes missing binaries and models, grants app permissions, runs one warm-up inference, then waits 200 s.
2. **30 runs:** measure, infer, pull logs, parse, then a 200 s cool-down.
3. **Teardown:** stops the logger app and restores the screen timeout.

The output goes to `experiment_runner/results/<name>/`:

- `run_table.csv`: one row per run, with all metrics plus `model_response`.
- One subfolder per run containing `llama_output.txt` (the llama.cpp log) and `run_logcat.txt` (the battery samples).

If the Wi-Fi drops or the run is interrupted, reconnect (`adb connect …`) and start the same command again. Experiment-Runner tracks finished runs in the `__done` column of `run_table.csv`.

**After each round:**

```bash
cp experiment_runner/results/<name>/run_table.csv experiment_runner/csv/<name>.csv
```

Then recharge the phone and repeat sections 12 and 13 for the next configuration. The 16 expected CSV names are listed in [`experiment_runner/csv/README.md`](../experiment_runner/csv/README.md).

**Workflow used for the paper:** instead of editing one config 16 times, the authors kept one folder per configuration. Each folder holds a copy of `RunnerConfig.py` with only that model uncommented and `WARMUP_MODEL` set to it, so each round's results stay in their own folder:

```
experiments_Q4_K_M/1_qwen2-0_5b/RunnerConfig.py   →  …/1_qwen2-0_5b/results/s25_llama_thesis_experiment/
experiments_Q4_K_M/2_qwen2.5-1.5b/RunnerConfig.py
…
experiments_IQ4_XS/8_gemma/RunnerConfig.py
```

Run each with `python <experiment-runner>/experiment-runner/ experiments_<quant>/<n>_<model>/RunnerConfig.py`. The layout inside `data/raw_logs_ER2.zip` follows this structure.

---

## 14. Aggregate results and plot

1. **Aggregate:** open [`experiment_runner/csv_processor.ipynb`](../experiment_runner/csv_processor.ipynb) from inside `experiment_runner/` and run all cells.
   - It loads the 16 files from `csv/` and computes the **median** of each metric across the 30 runs, plus the **IQR** of the speed, latency and energy metrics.
   - It writes `final_results.csv`.
2. **Add quality scores:** add two columns, `Final_BERTscore` and `Overall_G-Eval`, from section 15.
3. **Plot:** [`experiment_runner/Results/EDA.ipynb`](../experiment_runner/Results/EDA.ipynb) reads `final_results.xlsx` from its own folder.
   - The published `final_results.xlsx` is already there, so the notebook runs as-is.
   - To plot your own results, convert your CSV and overwrite it:

     ```bash
     python -c "import pandas as pd; pd.read_csv('experiment_runner/final_results.csv').to_excel('experiment_runner/Results/final_results.xlsx', index=False)"
     ```

Compare your output against the published `final_results.xlsx`.

---

## 15. Evaluate output quality

Decoding is greedy (`--temp 0`), so all 30 responses of a configuration are identical. Take one response per configuration:

```bash
python - <<'EOF'
import glob, pandas as pd
for f in sorted(glob.glob("experiment_runner/csv/*.csv"), key=lambda p: int(p.split("/")[-1].split("_")[0])):
    print(f.split("/")[-1], "|", pd.read_csv(f)["model_response"].iloc[0])
EOF
```

### 15.1 BERTScore (reference-based)

Paste the 16 responses into the `csv_data` block of [`quality_metrics/BERTscore.py`](../experiment_runner/quality_metrics/BERTscore.py), replacing the paper's responses. Then run it:

```bash
cd experiment_runner/quality_metrics
python BERTscore.py           # → scored_models.csv (roberta-large F1 vs. the gold summary)
```

BERTScore favors extractive copying, so small models that repeat the source text score high. This is why the paper relies on the judge below.

### 15.2 LLM-as-a-judge (G-Eval style, reference-free)

Paste the responses into `models_data` in [`quality_metrics/test_DeepEval.py`](../experiment_runner/quality_metrics/test_DeepEval.py). Then run it:

```bash
export OPENAI_API_KEY=...      # never commit this
python test_DeepEval.py        # → llm_a_judge_scores.csv
```

Use `python`, not `pytest`. The file runs from `__main__` and contains no test functions.

The judge scores all 16 responses relative to each other on four criteria: *Faithfulness*, *Relevance*, *Coherence* and *Overall_Quality*. The `Overall_Quality` score is reported as `Overall_G-Eval`, and `BERT_F1` as `Final_BERTscore`.

The paper's scores are in [`quality_metrics/results/`](../experiment_runner/quality_metrics/results/): `BERTscore.csv` and `llm_a_judge_scores.csv`.

The judge model is set in the `model=` argument (the paper used `gpt-5.2`). A different judge model will give different absolute scores.

---

## 16. Statistical analysis

The scripts used for the paper are in [`experiment_runner/statistics/`](../experiment_runner/statistics/). Each one reads its input from the current folder, so `cd` into the folder first. The paired comparisons match runs by repetition index.

### 16.1 Quantization: `Q4_K_M` vs `IQ4_XS`

```bash
cd experiment_runner/statistics/quantization
python wilcoxon.py     # Wilcoxon signed-rank on paired (Q4_K_M − IQ4_XS) differences, 6 metrics
python shapiro.py      # Shapiro-Wilk normality of those paired differences
```

- Input: `run_table_all.csv`, which is all 480 runs with a `quantization` column.
- `shapiro.py` tests one metric at a time. Change `values=` in the pivot (default `energy_per_token`) to test another.
- Expected output from `wilcoxon.py` (paper table):

| Metric | W | p |
|---|---|---|
| Generation speed | 11179 | 4.23e-03 |
| Total energy | 8967 | 3.36e-07 |
| Peak memory | 0 | 2.82e-41 |
| Time to first token | 899 | 2.24e-36 |
| Inference latency | 2966 | 1.32e-26 |

### 16.2 Models: Friedman + pairwise Wilcoxon (Holm)

```bash
cd experiment_runner/statistics/model_comparison
python wilcoxon_holm.py
```

The script does the following:

1. Runs the Friedman omnibus test across the 8 models.
2. Computes mean ranks.
3. Runs all 28 pairwise Wilcoxon signed-rank tests with Holm-Bonferroni correction.
4. Prints a ranked summary table and saves a p-value heatmap.

**Inputs:** one 60 × 8 matrix per metric, with blocks = 30 `Q4_K_M` + 30 `IQ4_XS` repetitions and columns = models:

- `Generation_speed.csv`
- `Total_Energy_Consumption.csv`
- `Peak_Memory.csv`
- `Inference_Latency.csv`
- `Time_to_FIrst_token.csv`
- `Energy_per_Token.csv`

Choose the metric by editing these two lines at the top of the script:

```python
FILENAME = 'Total_Energy_Consumption.csv'
LOWER_IS_BETTER = True     # set False for Generation_speed.csv
```

**Expected output for energy:** Friedman χ² = 415.84, p = 9.55e-86. Mean ranks: Qwen2-0.5B 1.00, OLMoE 2.05, Qwen2.5-1.5B 2.95, Phi-2 4.02, Qwen2.5-3B 4.98, Qwen2.5-7B 6.08, Llama-3.1-8B 6.98, Gemma-2-9B 7.93.

### 16.3 Rebuilding the inputs from your own runs

Both input formats can be built from the 16 per-run CSVs in `experiment_runner/csv/`:

```python
import pandas as pd

CSV = "experiment_runner/csv"
MODELS = {"qwen2-0_5b": "Qwen2-0.5B", "qwen2.5-1.5b": "Qwen2.5-1.5B", "phi-2": "Phi-2",
          "qwen2.5-3b": "Qwen2.5-3B", "OLMoE": "OLMoE-1B-7B-0125", "qwen2.5-7b": "Qwen2.5-7B",
          "llama": "Llama3.1-8B", "gemma": "Gemma2-9B"}

frames = []
for q, first in (("Q4_K_M", 1), ("IQ4_XS", 9)):
    for i, (key, name) in enumerate(MODELS.items()):
        df = pd.read_csv(f"{CSV}/{first + i}_{key}_{q}.csv")
        frames.append(df.assign(model_file=name, quantization=q, rep=range(len(df))))
runs = pd.concat(frames)

# 16.1 input
runs.to_csv("run_table_all.csv", index=False)

# 16.2 input, e.g. total energy
m = runs.pivot_table(index=["quantization", "rep"], columns="model_file", values="total_energy_consumption")
m.index = [f"{q}_repetition_{r}" for q, r in m.index]
m.rename_axis("Row Labels").to_csv("Total_Energy_Consumption.csv")
```

---

## 17. Troubleshooting

| Symptom | Fix |
|---|---|
| `CANNOT LINK EXECUTABLE "./llama-cli": library "libomp.so" not found` | Push `libomp.so` (section 5.2) and keep `LD_LIBRARY_PATH=.`. |
| Old binary still used after rebuilding | `RunnerConfig` skips files that already exist on the device. Run `adb shell rm /data/local/tmp/llama-cli /data/local/tmp/lib*.so` and run again. |
| `ModuleNotFoundError: EventManager` | Run via `python <experiment-runner>/experiment-runner/ …`, or `export PYTHONPATH=<experiment-runner>:<experiment-runner>/experiment-runner`. |
| Energy columns are `0` | The logger did not run or was killed. Re-run the deviceidle whitelist and the permission grants, check the smoke test in section 8, and enlarge the logcat buffer (`adb shell logcat -G 16M`). |
| Timing or memory columns are `0` | The llama.cpp output format differs; see section 10. |
| `adb: device offline` / Wi-Fi drop mid-round | `adb connect <PHONE_IP>:5555` and re-run. Finished runs are kept. |
| The phone's IP changes | Update `DEVICE_ID`. Some hotspots let you reserve a fixed IP. |
| The process is killed on 8–9B models | Out of memory. Close all apps, reboot the phone before the round, and use a device with ≥12 GB RAM. |
| The screen turns off | Check that `screen_off_timeout` was set (it happens in `before_experiment`), and disable any power-saving mode. |
| The judge API rejects `temperature` or `seed` | Some models don't accept these. Remove them from the `parse(...)` call and note the change. |
| A weak model loops or repeats | Expected for sub-1B models. Generation length is fixed at 100 tokens, so the energy numbers stay comparable. |

---

## 18. Appendix

### A. BatteryManager crash fix

The upstream companion app throws a `NullPointerException` when asked for an unmapped `BATTERY_*` property. If you build the APK from source, replace `getData()` in `DataCollecter.kt` with:

```kotlin
fun getData(): String {
    var data = ""
    val receiver: Intent? = context.registerReceiver(null, intentFilter)

    for (dataPoint in dataPoints) {
        if (dataPoint.startsWith("EXTRA")) {
            if (dataPoint == "EXTRA_BATTERY_LOW" || dataPoint == "EXTRA_PRESENT")
                data += "," + receiver?.getBooleanExtra(dataPointsMapEXTRA[dataPoint], false).toString()
            else if (dataPoint == "EXTRA_TECHNOLOGY")
                data += "," + receiver?.getStringExtra(dataPointsMapEXTRA[dataPoint]).toString()
            else
                data += "," + receiver?.getIntExtra(dataPointsMapEXTRA[dataPoint], Int.MIN_VALUE).toString()
        } else if (dataPoint == "ACTION_CHARGING") {
            data += "," + batteryManager.isCharging.toString()
        } else if (dataPoint == "ACTION_DISCHARGING") {
            data += "," + (!batteryManager.isCharging).toString()
        } else if (dataPoint.startsWith("BATTERY")) {
            val propertyId = dataPointsMapBATTERY[dataPoint]
            if (propertyId != null) {
                data += "," + batteryManager.getIntProperty(propertyId).toString()
            } else {
                android.util.Log.e("BatteryMgr", "Unknown BATTERY property requested: $dataPoint")
                data += ",0"
            }
        }
    }
    return "${System.currentTimeMillis()}" + data
}
```

The app targets JDK 17.

### B. How each metric is computed

| Metric | Source | Computation |
|---|---|---|
| Prefill speed (t/s), prefill latency (s), input tokens | `prompt eval time` line | as printed (ms → s) |
| Decode speed (t/s), generation latency (s), output tokens | `eval time` line | as printed |
| Time to first token (s) | | prefill latency + one decode step |
| Inference latency (s) | `total time` line | as printed |
| Avg current / voltage / power | battery samples | arithmetic mean, after baseline subtraction (current) |
| Total energy (J) | battery samples | trapezoidal integration of `P = I·V` over the timestamps |
| Energy per token (J/token) | | total energy ÷ output tokens |
| Peak memory, model weight, context, compute (MiB); KV cache (MiB) | llama.cpp memory breakdown and `llama_kv_cache` line | as printed |

### C. Known differences between the paper text and the code

Check these if your numbers differ:

- **Baseline:** the paper describes subtracting mean idle *power* measured over 2 h. The code subtracts a fixed idle *current* (0.10 A by default; section 11 replaces it with your measured value).
- **Battery window:** the paper says 80–100 %. Earlier notes used 90–100 %.
- **Device cleanup:** the paper says outputs are deleted from the device after each pull. The code deletes the previous llama log at the start of each run instead.
- **Warm-up wait:** `before_experiment` logs "Waiting for 400 seconds" but sleeps 200 s.
- **Input length:** the paper reports 93–119 input tokens across models (the tokenizers and chat templates differ).
