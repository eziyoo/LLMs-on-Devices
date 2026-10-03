# Reproducing the Research

This guide explains how to reproduce *"Sustainability Is Not Linear: Quantifying Performance, Energy, and Privacy Trade-offs in On-Device Intelligence"* in two ways:

- **Track A, reproduce the analysis (about 10 minutes, no phone).** Recompute every table, statistical test and figure from the published measurements in `data/`.
- **Track B, run the experiment yourself (about 2 days, needs an Android phone).** Measure energy, latency, memory and quality of LLMs on your own device with the same pipeline.

No rooting or hardware modification is needed.

---

## Contents

- [Repository layout](#repository-layout)
- **Track A:** [A. Reproduce the analysis](#a-reproduce-the-analysis)
- **Track B:**
  1. [Overview and time budget](#1-overview-and-time-budget)
  2. [Requirements](#2-requirements)
  3. [Host setup](#3-host-setup)
  4. [Build llama.cpp for Android](#4-build-llamacpp-for-android)
  5. [Prepare the models](#5-prepare-the-models)
  6. [Prepare the phone](#6-prepare-the-phone)
  7. [Connect over wireless ADB](#7-connect-over-wireless-adb)
  8. [Install the companion app](#8-install-the-companion-app)
  9. [Configure the experiment](#9-configure-the-experiment)
  10. [Sanity check](#10-sanity-check)
  11. [Measure the idle baseline](#11-measure-the-idle-baseline)
  12. [Run the experiment](#12-run-the-experiment)
  13. [Analyse your results](#13-analyse-your-results)
  14. [Evaluate output quality](#14-evaluate-output-quality)
- [Extending the study](#extending-the-study)
- [Methods in detail](METHODS.md)
- [Troubleshooting](#troubleshooting)
- [Appendix](#appendix)

---

## Repository layout

```
LLMs-on-Devices/
├── experiment/                    # Track B: drives the phone
│   ├── RunnerConfig.py            # Experiment-Runner configuration (the measurement pipeline)
│   ├── config.example.ini         # copy to config.ini: device, paths, model under test
│   ├── log_parsers.py             # parses llama.cpp and battery logs into metrics
│   ├── prepare_device.py          # installs the companion app and sets permissions
│   ├── sanity_check.py            # checks that llama.cpp prints everything the parsers need
│   ├── measure_baseline.py        # measures the phone's idle current
│   ├── settings.py                # shared config loading and adb helper
│   ├── companion_app/             # BatteryManager companion APK (on-device energy logger)
│   └── quantization/              # notebook: importance matrix + IQ4_XS quantization
├── analysis/                      # Track A (and the analysis step of Track B)
│   ├── aggregate.py               # runs → one row per configuration (median, IQR) + quality
│   ├── stat_tests.py              # Shapiro-Wilk, Wilcoxon, Friedman + Holm
│   ├── reparse_raw_logs.py        # re-derives data/runs/ from the raw logs
│   ├── figures.ipynb              # plots
│   └── quality/                   # bertscore.py, llm_judge.py
├── data/                          # all published measurements (see data/README.md)
│   ├── runs/                      # 16 per-run tables, 30 runs each
│   ├── raw/raw_logs.zip           # raw llama.cpp and battery logs
│   ├── quality/                   # scored responses and quality scores
│   └── aggregated/                # final_results.xlsx / .csv
├── archive/                       # early prototypes, not needed to reproduce the paper
├── docs/REPRODUCE.md              # this guide
└── requirements.txt
```

---

## A. Reproduce the analysis

You need Python 3.10+ only.

```bash
git clone https://github.com/eziyoo/LLMs-on-Devices.git
cd LLMs-on-Devices
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

| Step | Command | Output |
|---|---|---|
| 1. Check raw data integrity (optional) | `python analysis/reparse_raw_logs.py` | Re-parses all 480 raw runs and confirms they match `data/runs/` |
| 2. Aggregate | `python analysis/aggregate.py` | `data/aggregated/final_results.{xlsx,csv}` |
| 3. Statistics | `python analysis/stat_tests.py --heatmaps` | Paper tables in `analysis/output/` |
| 4. Figures | `cd analysis && jupyter notebook figures.ipynb` | Plots |

`stat_tests.py` reproduces the paper's statistical analysis:

- **Normality (Table "Shapiro-Wilk"):** Shapiro-Wilk on the paired Q4_K_M − IQ4_XS differences. For example, generation speed gives W = 0.7375 and energy W = 0.8800.
- **Quantization (Table "Wilcoxon"):** Wilcoxon signed-rank test, Q4_K_M vs IQ4_XS, paired by model and repetition. For example, memory gives W = 0, p = 2.82e-41, and energy W = 8967, p = 3.36e-07.
- **Models (Table "Friedman"):** Friedman test across the 8 models, then pairwise Wilcoxon tests with Holm-Bonferroni correction and mean ranks. The blocks are the 30 Q4_K_M plus 30 IQ4_XS repetitions per model. For example, generation speed gives χ² = 413.07 and energy χ² = 415.84.

The quality scores (`data/quality/`) come from section 14. They are already included, so Track A doesn't need an OpenAI key or a GPU.

---

## 1. Overview and time budget

```
 Host (laptop)                                   Android phone (unrooted)
 ┌──────────────────────────┐   wireless ADB    ┌────────────────────────────────┐
 │ Experiment-Runner        │ ───────────────►  │ /data/local/tmp/llama-cli      │
 │  └ experiment/           │                   │ /data/local/tmp/<model>.gguf   │
 │     RunnerConfig.py      │ ◄───────────────  │ BatteryManager companion app   │
 │     log_parsers.py       │  logs (pull)      │  current, voltage, temp @100 ms│
 └──────────────────────────┘                   └────────────────────────────────┘
```

For every run, `RunnerConfig.py` does the following:

1. Clears logcat.
2. Starts the battery logger (100 ms sampling) and waits 2 s.
3. Runs `llama-cli` with a fixed summarization prompt and generates exactly 100 tokens.
4. Stops the logger and pulls both logs to the host.
5. Parses them into one row of `run_table.csv`.
6. Waits 200 s to cool down.

**Design:** 8 models × 2 quantizations (`Q4_K_M`, `IQ4_XS`) = 16 configurations × 30 runs.

**Time:** one round (one configuration) takes about 2 hours, mostly cool-down, so all 16 take about 32 hours. Recharge the phone between rounds.

---

## 2. Requirements

### Hardware

| Item | Requirement | Used in the paper |
|---|---|---|
| Phone | Android, arm64, **≥12 GB RAM** (needed for the 7–9B models). Android 13+ recommended. | Samsung Galaxy S25 Ultra, Snapdragon 8 Elite, 12 GB, Android 16 |
| Host | macOS, Linux, or Windows with WSL2 | MacBook Air M4 |
| Network | A **third device** acting as a Wi-Fi hotspot that both the host and the phone join | A spare phone as hotspot |
| USB cable | Only for setup and copying models. It must be **unplugged** during measurements. | |

Do not use the target phone's own hotspot, because it adds radio power draw. University and public Wi-Fi networks usually block ADB.

### Software (host)

| Tool | Note |
|---|---|
| Python 3.10+ | |
| `git`, `cmake` ≥ 3.22, a C/C++ compiler | To build llama.cpp |
| Android SDK Platform-Tools (`adb`) | Must be on `PATH` |
| Android NDK | r29 was used |
| Hugging Face account | Llama 3.1 and Gemma 2 are gated; accept their licenses first |
| OpenAI API key | Only for the LLM-as-a-judge step |

### Disk space

- Host: about 60 GB (temporary FP16 conversions during quantization).
- Phone: room for the model of the current round. The largest is Gemma-2-9B Q4_K_M, about 5.8 GB.

---

## 3. Host setup

Clone this repository, Experiment-Runner and llama.cpp side by side:

```bash
mkdir -p ~/llm_on_device && cd ~/llm_on_device

git clone https://github.com/eziyoo/LLMs-on-Devices.git
git clone https://github.com/S2-group/experiment-runner.git
git clone https://github.com/ggml-org/llama.cpp.git

python3 -m venv venv && source venv/bin/activate
pip install -r LLMs-on-Devices/requirements.txt
pip install -r experiment-runner/requirements.txt

adb version     # check that adb works
```

---

## 4. Build llama.cpp for Android

### 4.1 Cross-compile `llama-cli`

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

This produces `build-android/bin/llama-cli` and several `lib*.so` files.

### 4.2 Add the OpenMP runtime

`llama-cli` needs `libomp.so`, which isn't on the phone. Copy it next to the binary. `RunnerConfig.py` pushes every `lib*.so` in that folder.

```bash
cp "$(find $ANDROID_NDK -path '*linux/aarch64/libomp.so' | head -n1)" build-android/bin/
git rev-parse HEAD > build-android/LLAMA_COMMIT.txt     # record the version you used
```

The parsers rely on llama.cpp's verbose output format. `experiment/sanity_check.py` (section 10) tells you if your version prints something different.

### 4.3 Host build (for quantizing)

```bash
cmake -B build && cmake --build build --config Release -j
```

---

## 5. Prepare the models

The pipeline expects these **exact filenames**:

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

Put them in one folder, for example `~/llm_on_device/models/`.

> **The filename selects the chat template.** `RunnerConfig.py` picks the prompt template from the lower-cased filename: `gemma`, `phi-2`, `llama-3`, `olmoe`, and Qwen ChatML for everything else. If you rename a file, keep that substring.

### Option A: quantize yourself (fully reproducible)

```bash
cd ~/llm_on_device
huggingface-cli login
huggingface-cli download Qwen/Qwen2.5-3B-Instruct --local-dir hf/Qwen2.5-3B-Instruct

# 1. Convert to FP16 GGUF
python llama.cpp/convert_hf_to_gguf.py hf/Qwen2.5-3B-Instruct --outfile f16/qwen2.5-3b-f16.gguf --outtype f16

# 2. Q4_K_M
llama.cpp/build/bin/llama-quantize f16/qwen2.5-3b-f16.gguf models/qwen2.5-3b-instruct-q4_k_m.gguf Q4_K_M

# 3. IQ4_XS (needs an importance matrix computed on calibration text, e.g. WikiText-2 train)
llama.cpp/build/bin/llama-imatrix -m f16/qwen2.5-3b-f16.gguf -f wiki.train.raw -o imatrix.dat
llama.cpp/build/bin/llama-quantize --imatrix imatrix.dat f16/qwen2.5-3b-f16.gguf models/Qwen2.5-3B-Instruct-IQ4_XS.gguf IQ4_XS
```

[`experiment/quantization/quantize_iq4_xs.ipynb`](../experiment/quantization/quantize_iq4_xs.ipynb) shows the full IQ4_XS flow for Phi-2. It runs on a free Kaggle GPU.

### Option B: pre-quantized GGUFs

Download the matching quantization from Hugging Face and rename it to the filename above. Different quantizers may use different calibration data, so Option A is preferred for exact replication.

---

## 6. Prepare the phone

1. **Developer options:** go to *Settings → About phone → Software information* and tap *Build number* 7 times. Then enable *USB debugging* and *Wireless debugging*.
2. **Isolate background activity:**
   - Turn off auto-sync, automatic app and system updates, Bluetooth, NFC, location and mobile data.
   - Turn on *Do Not Disturb* and close all apps.
3. **Display:** set minimum brightness and turn off adaptive brightness (`prepare_device.py --brightness-min` does this). The pipeline keeps the screen on during a round.
4. **Battery:** charge to 100 %, then unplug. Keep it between **80 % and 100 %** during a round.
5. **Thermals:** remove the case, lay the phone flat, keep it at a stable room temperature and out of the sun.

---

## 7. Connect over wireless ADB

USB must be unplugged during measurement, because the host would charge the phone and corrupt the discharge readings.

1. Turn on the hotspot of the **third device** and connect both the host and the phone to it.
2. **Copy the model of the round over USB first**, because pushing GBs over Wi-Fi is slow. The pipeline skips files that are already on the phone.
   ```bash
   adb push ~/llm_on_device/models/<model>.gguf /data/local/tmp/
   ```
3. Switch to wireless:
   ```bash
   adb tcpip 5555
   # unplug the USB cable
   adb connect <PHONE_IP>:5555     # Settings → About phone → Status → IP address
   adb devices                     # should list <PHONE_IP>:5555  device
   ```
   On Android 11+ you can also pair without USB: *Wireless debugging → Pair device with pairing code*, then `adb pair` and `adb connect`.

**WSL2:** attach the USB device to WSL first (`usbipd attach --wsl --busid <id>` in PowerShell).

---

## 8. Install the companion app

The [BatteryManager companion app](../experiment/companion_app/README.md) logs current, voltage, capacity and temperature through the Android `BatteryManager` API, without root. First create your config (section 9), then:

```bash
cd ~/llm_on_device/LLMs-on-Devices
python experiment/prepare_device.py --brightness-min
```

This installs the APK, grants the notification permission, exempts the app from battery optimisation (otherwise Samsung kills the service) and enlarges the logcat buffer.

---

## 9. Configure the experiment

```bash
cp experiment/config.example.ini experiment/config.ini
```

Edit `experiment/config.ini`:

| Key | Set to |
|---|---|
| `[device] device_id` | `<PHONE_IP>:5555`, exactly as `adb devices` shows it |
| `[paths] llama_build_dir` | `~/llm_on_device/llama.cpp/build-android/bin` |
| `[paths] model_dir` | Folder with the `.gguf` files |
| `[run] model` | **The model of this round**, one filename from section 5 |
| `[run] repetitions` | `30` |
| `[run] cooldown_seconds` | `200` |
| `[run] baseline_current_a` | Your idle current from section 11 (the paper used 0.10 A) |

These inference settings are fixed in `RunnerConfig.py`, as in the paper:

- `-n 100 --ignore-eos`, with the end-of-turn token banned via `--logit-bias`, so every run generates exactly 100 tokens.
- `-c 512 -t 8 --temp 0` (greedy decoding, 8 threads).
- The same summarization text for every model, in each model's chat template.
- One warm-up generation before the first run.

---

## 10. Sanity check

With the binary pushed (`adb push ~/llm_on_device/llama.cpp/build-android/bin/* /data/local/tmp/`) and the model on the phone:

```bash
python experiment/sanity_check.py
```

It runs a 32-token generation and checks for each line the parsers need: prefill timings, generation timings, total time, the `Parsed message` response, KV-cache size and the memory breakdown. If something is missing, your llama.cpp version prints a different format. Use an older commit or adapt the regexes in `experiment/log_parsers.py`.

---

## 11. Measure the idle baseline

Energy is reported **net of idle draw**: the phone's idle current is subtracted from every sample. Measure it under run conditions (screen on at minimum brightness, unplugged, wireless ADB connected, phone untouched):

```bash
python experiment/measure_baseline.py --minutes 60      # the paper used 2 hours
```

Copy the printed `baseline_current_a` into `experiment/config.ini`.

---

## 12. Run the experiment

Before each round, check that:

- the phone is 80–100 % charged and **unplugged**;
- `adb devices` lists it;
- `[run] model` in `config.ini` is the model of this round.

Then start the round:

```bash
cd ~/llm_on_device/LLMs-on-Devices
python ../experiment-runner/experiment-runner/ experiment/RunnerConfig.py
```

The round has three phases:

1. **Setup:** keep the screen on, push missing files, grant permissions, run one warm-up generation, wait 200 s.
2. **30 runs:** measure, infer, pull logs, parse, then cool down for 200 s.
3. **Teardown:** stop the logger and restore the screen timeout.

Results go to `experiment/results/<run-id>/`. The run ID comes from the model, e.g. `1_qwen2-0_5b_Q4_K_M`:

- `run_table.csv`: one row per run with all metrics (columns in [`data/README.md`](../data/README.md)).
- `run_0_repetition_<i>/llama_output.txt` and `run_logcat.txt`: the raw logs.

If Wi-Fi drops mid-round, reconnect (`adb connect …`) and start the same command again. Experiment-Runner tracks finished runs in the `__done` column.

**Between rounds:** recharge the phone, set the next `model` in `config.ini` and run again.

---

## 13. Analyse your results

Copy your run tables into `data/runs/` (replacing the published ones, or into a copy of the repo), then run the Track A steps:

```bash
for d in experiment/results/*/; do cp "$d/run_table.csv" "data/runs/$(basename "$d").csv"; done
python analysis/aggregate.py
python analysis/stat_tests.py --heatmaps
```

---

## 14. Evaluate output quality

Decoding is greedy, so all 30 responses of a configuration are identical. Every run generates 100 tokens, so the summary is followed by a continuation. Put the summary part of each configuration's response into `data/quality/evaluated_responses.csv` (columns `index, run_id, model, response`), then score it:

```bash
python analysis/quality/bertscore.py                 # → data/quality/bertscore_scores.csv
export OPENAI_API_KEY=...                            # never commit it
python analysis/quality/llm_judge.py                 # → data/quality/llm_judge_scores.csv
```

The two scores answer different questions:

- **BERTScore** (roberta-large F1 against a gold summary) is reference-based. It favours responses that copy the source text, which smaller models tend to do.
- **The LLM judge** is reference-free and G-Eval style. It scores all responses relative to each other on Faithfulness, Relevance, Coherence and Overall_Quality. The paper reports `Overall_Quality` as `Overall_G-Eval` and `BERT_F1` as `Final_BERTscore`.
- **Judge model:** the paper used `gpt-5.2`, set in the `model=` argument. A different judge model gives different absolute scores.

Then re-run `python analysis/aggregate.py` to merge the scores.

---

## Extending the study

The pipeline is not tied to the paper's device, models or task.

- **Another phone:** set its `device_id` in `config.ini`, measure its own baseline (section 11) and run the sanity check (section 10). Phones with less than 12 GB RAM will not fit the 7–9B models.
- **Another model:**
  1. Put the GGUF in `model_dir` and set `[run] model`.
  2. Add the filename and a new run ID to `MODEL_RUN_IDS` in `experiment/settings.py`. Without an entry, the results folder is named after the file.
  3. If the model uses a chat template not covered in `RunnerConfig.interact()` (Qwen ChatML, Phi-2, OLMoE, Llama-3, Gemma), add a branch with its template and end-of-turn token ID(s).
  4. To include it in the analysis, also add its label to `MODEL_LABELS` in `analysis/aggregate.py` and to `MODELS` in `analysis/stat_tests.py`.
- **Another task or prompt:** edit `context_text` and the instruction in `RunnerConfig.interact()`. Keep `-n 100 --ignore-eos` if you want the same fixed-length comparison.
- **GPU/NPU backends:** llama.cpp has GPU build options (e.g. Vulkan, OpenCL), but they were not used or tested in this study. Rebuild with the backend you want, then run `sanity_check.py`. The parsers need the same timing and memory lines, and the memory breakdown may print a different device line.

[`docs/METHODS.md`](METHODS.md) documents the workload, energy measurement, quality evaluation and statistics in detail.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `config.ini not found` | `cp experiment/config.example.ini experiment/config.ini` and edit it |
| `CANNOT LINK EXECUTABLE "./llama-cli": library "libomp.so" not found` | Copy `libomp.so` into the build folder (section 4.2) |
| An old binary is still used after rebuilding | Files already on the phone are skipped: `adb shell rm /data/local/tmp/llama-cli /data/local/tmp/lib*.so` |
| `ModuleNotFoundError: EventManager` | Run via `python <experiment-runner>/experiment-runner/ experiment/RunnerConfig.py` |
| Energy columns are `0` | The logger didn't run or was killed. Re-run `prepare_device.py` and check that `adb logcat -d \| grep BatteryMgr` shows `stats =>` lines. |
| Timing or memory columns are `0` | Run `sanity_check.py`; the llama.cpp output format differs |
| `adb: device offline` / Wi-Fi drop | `adb connect <PHONE_IP>:5555` and start the round again; finished runs are kept |
| The phone's IP changes | Update `device_id` in `config.ini` |
| The process is killed on 8–9B models | Out of memory. Close all apps, reboot before the round, and use ≥12 GB RAM. |
| The judge API rejects `temperature` or `seed` | Some models don't accept them. Remove them from the `parse(...)` call and note the change. |

---

## Appendix

### A. Companion app crash fix

Upstream BatteryManager companion code throws a `NullPointerException` for unmapped `BATTERY_*` properties. The fix (`DataCollector.getData()` appends `0` and logs an error instead of crashing) is on [eziyoo/batterymanager-companion, branch `fix-battery-property-crash`](https://github.com/eziyoo/batterymanager-companion/tree/fix-battery-property-crash). The APK in `experiment/companion_app/` is all you need to run the experiment.

### B. How each metric is computed

| Metric | Source | Computation |
|---|---|---|
| Prefill speed, prefill latency, input tokens | `prompt eval time` line | as printed (ms → s) |
| Decode speed, generation latency, output tokens | `eval time` line | as printed |
| Time to first token | | prefill latency + one decode step |
| Inference latency | `total time` line | as printed |
| Avg current / voltage / power | battery samples | mean, after subtracting the baseline current |
| Total energy (J) | battery samples | trapezoidal integration of `P = I·V` over the timestamps |
| Energy per token (J/token) | | total energy ÷ output tokens |
| Peak memory, model weight, context, compute; KV cache (MiB) | llama.cpp memory breakdown and `llama_kv_cache` line | as printed |

### C. Paper text vs. code

Check these if your numbers differ:

- **Baseline:** the paper describes subtracting mean idle *power*. The code subtracts the mean idle *current* from each sample before multiplying by voltage (`baseline_current_a`, 0.10 A in the paper's runs).
- **Device cleanup:** the paper says outputs are deleted from the device after each pull. The code deletes the previous llama log at the start of each run.
- **Input length:** 93–119 input tokens across models, because tokenizers and chat templates differ.
