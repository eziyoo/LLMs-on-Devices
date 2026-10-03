# Reproduction Guide

A step-by-step roadmap for reproducing *"Sustainability Is Not Linear: Quantifying Performance, Energy, and Privacy Trade-offs in On-Device Intelligence"*.

There are two ways to use this repository:

| | Track A: reproduce the analysis | Track B: run the experiment yourself |
|---|---|---|
| **What you get** | Every table, statistical test and figure of the paper, recomputed from the published measurements | Your own energy, latency, memory and quality measurements on your own phone |
| **You need** | A computer with Python 3.10+ | An Android phone (≥12 GB RAM), a computer, a spare device for a Wi-Fi hotspot |
| **Time** | ≈ 10 minutes | ≈ 1 day of setup + ≈ 32 hours of unattended measurement |
| **Start at** | [Track A](#track-a-reproduce-the-analysis) | [Roadmap](#track-b-roadmap) |

No rooting and no hardware modification are needed for either track.

---

## Contents

- [Repository layout](#repository-layout)
- [Track A: reproduce the analysis](#track-a-reproduce-the-analysis)
- [Track B: roadmap](#track-b-roadmap)
  - [Phase 0: Prerequisites](#phase-0-prerequisites)
  - [Phase 1: Host setup](#phase-1-host-setup)
  - [Phase 2: Build llama.cpp for Android](#phase-2-build-llamacpp-for-android)
  - [Phase 3: Prepare the models](#phase-3-prepare-the-models)
  - [Phase 4: Prepare the phone](#phase-4-prepare-the-phone)
  - [Phase 5: Connect over wireless ADB](#phase-5-connect-over-wireless-adb)
  - [Phase 6: Configure and calibrate](#phase-6-configure-and-calibrate)
  - [Phase 7: Run the 16 rounds](#phase-7-run-the-16-rounds)
  - [Phase 8: Analyse your results](#phase-8-analyse-your-results)
  - [Phase 9: Evaluate output quality](#phase-9-evaluate-output-quality)
- [How a round works](#how-a-round-works)
- [Extending the study](#extending-the-study)
- [Troubleshooting](#troubleshooting)
- [Appendix](#appendix)

Background on *why* the method looks the way it does is in [`METHODS.md`](METHODS.md).

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
├── analysis/                      # Track A, and Phase 8–9 of Track B
│   ├── aggregate.py               # runs → one row per configuration (median, IQR) + quality
│   ├── stat_tests.py              # Shapiro-Wilk, Wilcoxon, Friedman + Holm, effect sizes
│   ├── reparse_raw_logs.py        # re-derives data/runs/ from the raw logs
│   ├── figures.ipynb              # plots
│   └── quality/                   # bertscore.py, llm_judge.py
├── data/                          # all published measurements (see data/README.md)
│   ├── runs/                      # 16 per-run tables, 30 runs each
│   ├── raw/raw_logs.zip           # raw llama.cpp and battery logs
│   ├── quality/                   # scored responses and quality scores
│   └── aggregated/                # final_results.xlsx / .csv
├── docs/                          # this guide, METHODS.md
└── archive/                       # early prototypes, not needed to reproduce the paper
```

---

## Track A: reproduce the analysis

**1. Install:**

```bash
git clone https://github.com/eziyoo/LLMs-on-Devices.git
cd LLMs-on-Devices
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

**2. Run the analysis:**

| Step | Command | ✅ Check |
|---|---|---|
| Raw data integrity (optional) | `python analysis/reparse_raw_logs.py` | `480 runs checked: 0 mismatching numeric values` |
| Aggregate | `python analysis/aggregate.py` | Writes `data/aggregated/final_results.{xlsx,csv}` |
| Statistics | `python analysis/stat_tests.py --heatmaps` | Friedman χ² = 413.07 (speed), 415.84 (energy), 420.00 (memory), 417.78 (latency), 415.46 (TTFT); tables in `analysis/output/` |
| Figures | `cd analysis && jupyter notebook figures.ipynb` | Plots render |

What `stat_tests.py` reports:
- **Normality:** Shapiro-Wilk on the paired Q4_K_M − IQ4_XS differences.
- **Quantization:** Wilcoxon signed-rank test, Q4_K_M vs IQ4_XS, paired by model and repetition, with rank-biserial effect sizes.
- **Models:** Friedman test across the 8 models, followed by pairwise Wilcoxon tests with Holm-Bonferroni correction, mean ranks and effect sizes.

Track A needs no OpenAI key and no GPU: the quality scores are already in `data/quality/`.

---

## Track B: roadmap

| Phase | What you do | Time | ✅ Done when |
|---|---|---|---|
| [0 Prerequisites](#phase-0-prerequisites) | Gather hardware and accounts | — | Checklist complete |
| [1 Host setup](#phase-1-host-setup) | Clone 3 repositories, install Python packages | 15 min | `adb version` works |
| [2 Build llama.cpp](#phase-2-build-llamacpp-for-android) | Cross-compile `llama-cli` for Android | 20 min | `build-android/bin/llama-cli` and `libomp.so` exist |
| [3 Models](#phase-3-prepare-the-models) | Download and quantize 8 models × 2 formats | 2–4 h | 16 `.gguf` files with the exact names |
| [4 Phone](#phase-4-prepare-the-phone) | Developer options, background isolation, display, battery | 20 min | Settings checklist done |
| [5 Connect](#phase-5-connect-over-wireless-adb) | Hotspot + wireless ADB | 10 min | `adb devices` lists `<IP>:5555` |
| [6 Configure & calibrate](#phase-6-configure-and-calibrate) | `config.ini`, companion app, sanity check, idle baseline | 1–2 h | All three helper scripts succeed |
| [7 Run](#phase-7-run-the-16-rounds) | 16 rounds × 30 runs | ≈ 2 h per round | 16 `run_table.csv` files |
| [8 Analyse](#phase-8-analyse-your-results) | Aggregate + statistics | 5 min | Tables in `analysis/output/` |
| [9 Quality](#phase-9-evaluate-output-quality) | BERTScore + LLM judge | 30 min | Scores in `data/quality/` |

---

### Phase 0: Prerequisites

**Hardware**

| Item | Requirement | Used in the paper |
|---|---|---|
| Phone | Android, arm64, **≥12 GB RAM** (needed for the 7–9B models); Android 13+ recommended | Samsung Galaxy S25 Ultra, Snapdragon 8 Elite, 12 GB, Android 16 |
| Computer (host) | macOS, Linux, or Windows with WSL2 | MacBook Air M4 |
| Hotspot device | Any second phone or router that both the computer and the test phone can join | A spare phone |
| USB cable | Only for setup and copying models; **unplugged** while measuring | |

**Software and accounts**

- [ ] Python 3.10+, `git`, `cmake` ≥ 3.22 and a C/C++ compiler
- [ ] [Android SDK Platform-Tools](https://developer.android.com/tools/releases/platform-tools) (`adb` on your `PATH`)
- [ ] [Android NDK](https://developer.android.com/ndk/downloads) (r29 was used)
- [ ] A Hugging Face account with access accepted for `meta-llama/Llama-3.1-8B-Instruct` and `google/gemma-2-9b-it` (gated models)
- [ ] An OpenAI API key, only for Phase 9
- [ ] About 60 GB free disk on the computer, and space on the phone for the model of the current round (largest: Gemma-2-9B Q4_K_M, ≈ 5.8 GB)

> **Why a separate hotspot?** Measurements must run without a USB cable, because a cable charges the phone and corrupts the battery readings. The phone's own hotspot would add radio power draw, and university or public Wi-Fi networks usually block ADB.

---

### Phase 1: Host setup

1. Clone this repository, Experiment-Runner and llama.cpp side by side:
   ```bash
   mkdir -p ~/llm_on_device && cd ~/llm_on_device
   git clone https://github.com/eziyoo/LLMs-on-Devices.git
   git clone https://github.com/S2-group/experiment-runner.git
   git clone https://github.com/ggml-org/llama.cpp.git
   ```
2. Create a Python environment and install both requirement files:
   ```bash
   python3 -m venv venv && source venv/bin/activate
   pip install -r LLMs-on-Devices/requirements.txt
   pip install -r experiment-runner/requirements.txt
   ```

✅ **Check:** `adb version` prints a version number.

---

### Phase 2: Build llama.cpp for Android

1. Cross-compile `llama-cli` for arm64:
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
2. Copy the OpenMP runtime next to the binary, because the phone doesn't have it. The pipeline pushes every `lib*.so` in this folder.
   ```bash
   cp "$(find $ANDROID_NDK -path '*linux/aarch64/libomp.so' | head -n1)" build-android/bin/
   ```
3. Record the llama.cpp version you built:
   ```bash
   git rev-parse HEAD > build-android/LLAMA_COMMIT.txt
   ```
4. To quantize models yourself (Phase 3, Option A), also build llama.cpp for the computer:
   ```bash
   cmake -B build && cmake --build build --config Release -j
   ```

✅ **Check:** `ls build-android/bin/` shows `llama-cli`, several `lib*.so` and `libomp.so`.

---

### Phase 3: Prepare the models

The pipeline expects these **exact file names**. Put all 16 in one folder, for example `~/llm_on_device/models/`.

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

> **Keep the names.** The file name selects the chat template: `gemma`, `phi-2`, `llama-3`, `olmoe`, otherwise Qwen ChatML. If you rename a file, keep that part of the name.

**Option A: quantize yourself (recommended for exact replication).** Shown for Qwen2.5-3B; repeat for each model.

```bash
cd ~/llm_on_device
huggingface-cli login
huggingface-cli download Qwen/Qwen2.5-3B-Instruct --local-dir hf/Qwen2.5-3B-Instruct

# 1. Convert to an FP16 GGUF
python llama.cpp/convert_hf_to_gguf.py hf/Qwen2.5-3B-Instruct --outfile f16/qwen2.5-3b-f16.gguf --outtype f16

# 2. Q4_K_M
llama.cpp/build/bin/llama-quantize f16/qwen2.5-3b-f16.gguf models/qwen2.5-3b-instruct-q4_k_m.gguf Q4_K_M

# 3. IQ4_XS: first an importance matrix from calibration text (e.g. WikiText-2 train), then quantize
llama.cpp/build/bin/llama-imatrix -m f16/qwen2.5-3b-f16.gguf -f wiki.train.raw -o imatrix.dat
llama.cpp/build/bin/llama-quantize --imatrix imatrix.dat f16/qwen2.5-3b-f16.gguf models/Qwen2.5-3B-Instruct-IQ4_XS.gguf IQ4_XS
```

[`experiment/quantization/quantize_iq4_xs.ipynb`](../experiment/quantization/quantize_iq4_xs.ipynb) runs the full IQ4_XS flow for Phi-2 on a free Kaggle GPU.

**Option B: pre-quantized files.** Download the matching quantization from Hugging Face and rename it to the name in the table. Quantizers may use different calibration data, so results can differ slightly.

✅ **Check:** `ls ~/llm_on_device/models/*.gguf | wc -l` prints `16`.

---

### Phase 4: Prepare the phone

1. **Developer options:** *Settings → About phone → Software information*, tap *Build number* 7 times. Then turn on *USB debugging* and *Wireless debugging* in *Developer options*.
2. **Background isolation:**
   - Turn off auto-sync, automatic app and system updates, Bluetooth, NFC, location and mobile data.
   - Turn on *Do Not Disturb* and close all apps.

   *Why:* Android regularly wakes background services (Google services, app updates, bug reports). They use CPU and battery and would add noise to the measurements.
3. **Display:** set the minimum brightness and turn off adaptive brightness (`prepare_device.py --brightness-min` in Phase 6 does this too). The pipeline keeps the screen on during a round.

   *Why:* when the screen turns off, Android assumes the phone is idle and throttles the CPU. In preliminary tests, CPU power dropped by about half.
4. **Battery:** charge to 100 %, then unplug.

   *Why:* battery voltage falls as charge drops (≈ 4.4 V when full). Running one model per round within 80–100 % keeps all models under similar electrical conditions.
5. **Thermals:** remove the case, lay the phone flat, keep it at a stable room temperature and out of direct sunlight.

✅ **Check:** all five items done.

---

### Phase 5: Connect over wireless ADB

1. Turn on the hotspot of the **spare device** and connect both the computer and the test phone to it.
2. With the USB cable still plugged in, copy the llama.cpp binaries and the first model to the phone (copying gigabytes over Wi-Fi is slow; the pipeline skips files that are already there):
   ```bash
   adb push ~/llm_on_device/llama.cpp/build-android/bin/* /data/local/tmp/
   adb push ~/llm_on_device/models/qwen2-0_5b-instruct-q4_k_m.gguf /data/local/tmp/
   ```
3. Switch ADB to Wi-Fi and unplug:
   ```bash
   adb tcpip 5555
   # unplug the USB cable now
   adb connect <PHONE_IP>:5555        # IP: Settings → About phone → Status → IP address
   ```
   On Android 11+ you can instead pair without a cable: *Wireless debugging → Pair device with pairing code*, then `adb pair` and `adb connect`. On WSL2, attach the USB device to WSL first (`usbipd attach --wsl --busid <id>` in PowerShell).

✅ **Check:** `adb devices` lists `<PHONE_IP>:5555    device`.

---

### Phase 6: Configure and calibrate

Run all commands from the repository folder: `cd ~/llm_on_device/LLMs-on-Devices`.

1. **Create your configuration:**
   ```bash
   cp experiment/config.example.ini experiment/config.ini
   ```
   Edit `experiment/config.ini`:

   | Key | Set to |
   |---|---|
   | `[device] device_id` | `<PHONE_IP>:5555`, exactly as `adb devices` shows it |
   | `[paths] llama_build_dir` | `~/llm_on_device/llama.cpp/build-android/bin` |
   | `[paths] model_dir` | `~/llm_on_device/models` |
   | `[run] model` | The model of the first round: `qwen2-0_5b-instruct-q4_k_m.gguf` |
   | `[run] repetitions` | `30` |
   | `[run] cooldown_seconds` | `200` |
   | `[run] baseline_current_a` | Leave `0.10` for now; step 4 measures your own value |

2. **Install the companion app** (the on-device energy logger) and set its permissions:
   ```bash
   python experiment/prepare_device.py --brightness-min
   ```
   ✅ **Check:** every line ends in `ok`.

3. **Check the llama.cpp output:**
   ```bash
   python experiment/sanity_check.py
   ```
   ✅ **Check:** six `[ok]` lines and `All lines found`. If a line is `MISSING`, your llama.cpp version prints a different format. Use an older llama.cpp version, or adapt the regexes in `experiment/log_parsers.py`.

4. **Measure the idle baseline.** Energy is reported net of what the phone uses when idle. Leave the phone untouched (screen on, minimum brightness, unplugged) and run:
   ```bash
   python experiment/measure_baseline.py --minutes 60      # the paper used 2 hours
   ```
   ✅ **Check:** it prints `baseline_current_a = …`. Copy that value into `config.ini`.

---

### Phase 7: Run the 16 rounds

One **round** = one model in one quantization, 30 runs, about 2 hours. The round runs unattended; see [How a round works](#how-a-round-works) for what happens inside.

**Pre-flight checklist, before every round**

- [ ] Battery between 80 % and 100 %, cable **unplugged**
- [ ] Screen on, minimum brightness, *Do Not Disturb* on, no apps open
- [ ] `adb devices` lists the phone
- [ ] `[run] model` in `config.ini` is the model of this round
- [ ] The model file is on the phone (`adb shell ls /data/local/tmp/*.gguf`), or in `model_dir` so it can be pushed

**Start the round:**

```bash
cd ~/llm_on_device/LLMs-on-Devices
source ../venv/bin/activate
python ../experiment-runner/experiment-runner/ experiment/RunnerConfig.py
```

✅ **Check:** the round ends with `All experiments complete.`, and `experiment/results/<run-id>/run_table.csv` has 30 rows with `__done = DONE`.

If Wi-Fi drops, reconnect (`adb connect <PHONE_IP>:5555`) and run the same command again; finished runs are kept.

**Between rounds:** recharge the phone to 100 %, unplug, delete the previous model from the phone if storage is tight (`adb shell rm /data/local/tmp/<old>.gguf`), set the next `model` and start again.

**Round checklist**

| ✓ | Run ID | `[run] model` |
|---|---|---|
| ☐ | `1_qwen2-0_5b_Q4_K_M` | `qwen2-0_5b-instruct-q4_k_m.gguf` |
| ☐ | `2_qwen2.5-1.5b_Q4_K_M` | `qwen2.5-1.5b-instruct-q4_k_m.gguf` |
| ☐ | `3_phi-2_Q4_K_M` | `phi-2.Q4_K_M.gguf` |
| ☐ | `4_qwen2.5-3b_Q4_K_M` | `qwen2.5-3b-instruct-q4_k_m.gguf` |
| ☐ | `5_OLMoE_Q4_K_M` | `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` |
| ☐ | `6_qwen2.5-7b_Q4_K_M` | `qwen2.5-7b-instruct-q4_k_m.gguf` |
| ☐ | `7_llama_Q4_K_M` | `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` |
| ☐ | `8_gemma_Q4_K_M` | `gemma-2-9b-it-Q4_K_M.gguf` |
| ☐ | `9_qwen2-0_5b_IQ4_XS` | `Qwen2-0.5b-instruct-iq4_xs.gguf` |
| ☐ | `10_qwen2.5-1.5b_IQ4_XS` | `Qwen2.5-1.5B-Instruct-IQ4_XS.gguf` |
| ☐ | `11_phi-2_IQ4_XS` | `Phi-2-iq4_xs.gguf` |
| ☐ | `12_qwen2.5-3b_IQ4_XS` | `Qwen2.5-3B-Instruct-IQ4_XS.gguf` |
| ☐ | `13_OLMoE_IQ4_XS` | `OLMoE-1B-7B-0125-Instruct-i1-IQ4_XS.gguf` |
| ☐ | `14_qwen2.5-7b_IQ4_XS` | `Qwen2.5-7B-Instruct-IQ4_XS.gguf` |
| ☐ | `15_llama_IQ4_XS` | `Meta-Llama-3.1-8B-Instruct-IQ4_XS.gguf` |
| ☐ | `16_gemma_IQ4_XS` | `gemma-2-9b-it-IQ4_XS.gguf` |

---

### Phase 8: Analyse your results

1. Copy your 16 run tables into `data/runs/`, replacing the published ones (or work in a separate copy of the repository):
   ```bash
   for d in experiment/results/*/; do cp "$d/run_table.csv" "data/runs/$(basename "$d").csv"; done
   ```
2. Run the analysis exactly as in Track A:
   ```bash
   python analysis/aggregate.py
   python analysis/stat_tests.py --heatmaps
   ```

✅ **Check:** `analysis/output/` contains `quantization_tests.csv`, `friedman_tests.csv` and the per-metric ranking tables.

---

### Phase 9: Evaluate output quality

Decoding is greedy, so all 30 runs of a configuration produce the same response. Generation is fixed at 100 tokens, so models continue writing after their summary.

1. For each configuration, put the summary part of the response (the text before the model starts an unrelated continuation) into `data/quality/evaluated_responses.csv` (columns `index, run_id, model, response`).
2. Score the responses:
   ```bash
   python analysis/quality/bertscore.py      # → data/quality/bertscore_scores.csv
   export OPENAI_API_KEY=...                 # never commit this
   python analysis/quality/llm_judge.py      # → data/quality/llm_judge_scores.csv
   ```
3. Merge the scores into the summary table: `python analysis/aggregate.py`.

✅ **Check:** `data/aggregated/final_results.xlsx` has `Final_BERTscore` and `Overall_G-Eval` filled in for all 16 rows.

Judge model, prompts and settings are documented in [`METHODS.md` §6](METHODS.md#6-output-quality). The paper used `gpt-5.2`; a different judge model gives different absolute scores.

---

## How a round works

A round is controlled by `experiment/RunnerConfig.py` through [Experiment-Runner](https://github.com/S2-group/experiment-runner) events. Setup runs **once**; the measurement loop runs **once per repetition**.

```
 BEFORE_EXPERIMENT ─┐  (once)
                    ▼
 ┌─► START_RUN ─► START_MEASUREMENT ─► INTERACT ─► STOP_MEASUREMENT ─► POPULATE_RUN_DATA ─┐
 │                                                                                        │
 └──────────────────────────────── 200 s cool-down ◄──────────────────────────────────────┘
                    │  (after 30 repetitions)
                    ▼
 AFTER_EXPERIMENT     (once)
```

| Stage | What happens | Why |
|---|---|---|
| **Before experiment** (once) | Clear logcat. Keep the screen on. Push the binary, libraries and the model if they are missing. Grant the companion app its permissions. One warm-up generation, then a 200 s pause. | A clean log, a phone that doesn't throttle, and no cold-start effects (first-load caches, CPU frequency ramp-up) in the first measured run. |
| **Start run** | Clear logcat again. | Each run's logs contain only that run, so runs can't mix. |
| **Start measurement** | Start the companion app's logging service (sample every 100 ms), then wait 2 s. | The logger stabilises before inference begins. |
| **Interact** | Delete the previous output file on the phone. Build the model-specific prompt and run `llama-cli` with fixed settings. Pull its output to the computer. | Instruction-tuned models expect their own chat template. Removing old output keeps runs isolated. |
| **Stop measurement** | Stop the logging service and save the logcat dump (the battery samples) on the computer. | The energy window ends right after generation. |
| **Populate run data** | Parse timings, memory and the response from the llama.cpp log. Subtract the idle baseline from every battery sample and integrate power over time (trapezoidal rule). Write one row of `run_table.csv`. | Net energy reflects only the model's work. |
| **Cool-down** | Wait 200 s. | The phone returns to its baseline temperature; 200 s was enough to prevent throttling in preliminary tests. |
| **After experiment** (once) | Clear logcat, force-stop the companion app, restore a 2-minute screen timeout. | The phone is back to normal use. |

Experiment-Runner also has a `BEFORE_RUN` event. It is not used, because all preparation happens once in *Before experiment*.

Fixed generation settings for every run: `-n 100 --ignore-eos` (end-of-turn token banned via `--logit-bias`), `-c 512 -t 8 --temp 0`. The reasons for each are in [`METHODS.md` §2](METHODS.md#2-experimental-controls).

---

## Extending the study

The pipeline is not tied to the paper's device, models or task.

- **Another phone:** set its `device_id` in `config.ini`, measure its own baseline (Phase 6, step 4) and run the sanity check. Phones with less than 12 GB RAM will not fit the 7–9B models.
- **Another model:**
  1. Put the GGUF in `model_dir` and set `[run] model`.
  2. Add the file name and a new run ID to `MODEL_RUN_IDS` in `experiment/settings.py`. Without an entry, the results folder is named after the file.
  3. If the model uses a chat template not covered in `RunnerConfig.interact()` (Qwen ChatML, Phi-2, OLMoE, Llama-3, Gemma), add a branch with its template and end-of-turn token ID(s).
  4. To include it in the analysis, also add its label to `MODEL_LABELS` in `analysis/aggregate.py` and to `MODELS` in `analysis/stat_tests.py`.
- **Another task or prompt:** edit `context_text` and the instruction in `RunnerConfig.interact()`. Keep `-n 100 --ignore-eos` if you want the same fixed-length comparison.
- **GPU/NPU backends:** llama.cpp has GPU build options (e.g. Vulkan, OpenCL), but they were not used or tested in this study. Rebuild with the backend you want, then run `sanity_check.py`. The parsers need the same timing and memory lines.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `config.ini not found` | `cp experiment/config.example.ini experiment/config.ini` and edit it |
| `CANNOT LINK EXECUTABLE "./llama-cli": library "libomp.so" not found` | Copy `libomp.so` into the build folder (Phase 2, step 2) and push it |
| An old binary is still used after rebuilding | Files already on the phone are skipped: `adb shell rm /data/local/tmp/llama-cli /data/local/tmp/lib*.so` |
| `ModuleNotFoundError: EventManager` | Start rounds with `python <experiment-runner>/experiment-runner/ experiment/RunnerConfig.py` |
| Energy columns are `0` | The logger didn't run or was killed. Re-run `prepare_device.py` and check that `adb logcat -d \| grep BatteryMgr` shows `stats =>` lines. |
| Timing or memory columns are `0` | Run `sanity_check.py`; the llama.cpp output format differs |
| The screen turned off during a round | Turn off power-saving mode and check *Settings → Display → Screen timeout*. The round sets the timeout at start; re-run the round. |
| Battery fell below 80 % during a round | Finish or stop the round, recharge to 100 % and re-run that round, so all rounds share the same voltage range |
| `adb: device offline` / Wi-Fi drop | `adb connect <PHONE_IP>:5555` and start the round again; finished runs are kept |
| The phone's IP changes | Update `device_id` in `config.ini` |
| The process is killed on 8–9B models | Out of memory: close all apps, reboot before the round, use a phone with ≥12 GB RAM |
| The judge API rejects `temperature` or `seed` | Some models don't accept them; remove them from the `parse(...)` call and note the change |

---

## Appendix

### A. How each metric is computed

| Metric | Source | Computation |
|---|---|---|
| Prefill speed, prefill latency, input tokens | `prompt eval time` line of `llama-cli -v` | as printed (ms → s) |
| Decode speed, generation latency, output tokens | `eval time` line | as printed |
| Time to first token | | prefill latency + one decode step |
| Inference latency | `total time` line | as printed |
| Avg current / voltage / power | battery samples | mean, after subtracting the baseline current |
| Total energy (J) | battery samples | trapezoidal integration of P = I·V over the timestamps |
| Energy per token (J/token) | | total energy ÷ output tokens |
| Peak memory, model weight, context, compute; KV cache (MiB) | llama.cpp memory breakdown and `llama_kv_cache` line | as printed |

Column names and units for every file are in [`data/README.md`](../data/README.md).

### B. Paper text vs. code

- **Baseline:** the paper describes subtracting mean idle power. The code subtracts the mean idle *current* from each sample before multiplying by voltage (`baseline_current_a`, 0.10 A in the paper's runs).
- **Device cleanup:** the paper says outputs are deleted from the phone after each pull. The code deletes the previous output at the start of each run, which has the same effect.
