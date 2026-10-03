<p align="center">
  <img src="https://github.com/eziyoo/LLMs-on-Devices/raw/main/figures/app_icon.png" alt="App Icon" width="200">
</p>

# 🌱 Sustainability Is Not Linear!

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10](https://img.shields.io/badge/python-3.10-blue.svg)]()
[![Platform: Android](https://img.shields.io/badge/Platform-Android_16-green.svg)]()

> **Note:** This repository contains the experimental pipeline and configuration scripts for the paper: *"Sustainability Is Not Linear: Quantifying Performance, Energy, and Privacy Trade-offs in On-Device Intelligence"*. This work was authored by Eziyo Ehsani, Luca Giamattei, Ivano Malavolta, and Roberto Pietrantuono.

## 📖 Overview
Deploying Large Language Models (LLMs) on mobile devices promises enhanced privacy, low latency, and offline accessibility, but is fundamentally constrained by limited memory, thermal headroom, and battery capacity. 

This project provides a reproducible experimental pipeline to systematically evaluate the trade-offs between energy consumption, inference latency, memory footprint, and generation quality for on-device LLMs. It utilizes a non-intrusive energy profiling approach based on Android's BatteryManager API, testing eight open-source models ranging from 0.5B to 9B parameters.

## 🚀 Key Findings
* **The Quantization-Energy Paradox:** While importance-aware quantization (IQ4_XS) significantly reduces peak memory, it does not consistently reduce end-to-end energy on CPU-based inference compared to mixed-precision formats (Q4_K_M). De-quantization overhead can offset memory bandwidth savings.
* **Architecture > Parameter Count:** Model architecture and active computation per token are stronger predictors of on-device energy and latency than the specific 4-bit quantization variant. 
* **The Promise of Sparsity:** Mid-sized and sparse models (e.g., Mixture-of-Experts) achieve favorable quality-per-joule trade-offs compared to larger dense counterparts.
* **Metric Bias:** Reference-based evaluation metrics (BERTScore) exhibit extractive bias in this setting, occasionally favoring smaller models that copy input text. Reference-free LLM-as-a-judge protocols (G-Eval) better reflect abstractive quality and coherence.

## 🛠 Experimental Setup
### Hardware
* **Device:** Samsung Galaxy S25 Ultra
* **SoC:** Qualcomm Snapdragon 8 Elite
* **RAM:** 12 GB
* **OS:** Android 16

### Software Stack
* **Inference Engine:** `llama.cpp` (CPU-only inference).
* **Orchestration:** `Experiment Runner` framework via Python.
* **Telemetry:** On-device Android BatteryManager API monitoring via Wireless ADB.

## ⚙️ Methodology & Pipeline
The core of this repository is the `RunnerConfig.py` script, which automates a strict, isolated experimental loop to ensure reproducible energy measurements on an unrooted device. 

The pipeline strictly enforces:
1. **Device State Control:** Forces the screen on at minimum brightness and disables background activity to prevent OS heuristics from skewing CPU power usage.
2. **Measurement Synchronization:** Starts the BatteryManager service with a fixed 2-second spin-up before inference and terminates it immediately after text generation to minimize capturing post-inference idle tail power.
3. **Energy Integration:** Captures voltage and current at 100ms intervals (10Hz), subtracts baseline idle power, and calculates net energy consumed (Joules) using trapezoidal integration.
4. **Thermal Management:** Enforces a 200-second cool-down period between runs to reduce thermal carryover and mitigate throttling effects.

## 📊 Evaluated Models
Models evaluated under `Q4_K_M` and `IQ4_XS` quantization schemes:
* Qwen2-0.5B
* Qwen2.5-1.5B
* Phi-2 (2.78B)
* Qwen2.5-3B
* OLMoE-1B-7B (6.919B)
* Qwen2.5-7B
* Meta-Llama-3.1-8B
* Gemma-2-9B

## 💻 Getting Started
**📘 Full step-by-step guide: [`docs/REPRODUCE.md`](docs/REPRODUCE.md)** (requirements, llama.cpp build, models, phone setup, baseline, running, analysis, troubleshooting).

Quick start:
```bash
git clone https://github.com/eziyoo/LLMs-on-Devices.git
git clone https://github.com/S2-group/experiment-runner.git
python3 -m venv venv && source venv/bin/activate
pip install -r LLMs-on-Devices/requirements.txt -r experiment-runner/requirements.txt
# build llama.cpp for Android, prepare models and the phone (see the guide), edit experiment_runner/RunnerConfig.py, then:
cd LLMs-on-Devices && python ../experiment-runner/experiment-runner/ experiment_runner/RunnerConfig.py
```

## 📂 Repository Structure
| Path | Content |
|---|---|
| `experiment_runner/RunnerConfig.py` | The measurement pipeline (Experiment-Runner configuration) |
| `experiment_runner/csv/` | Per-run result tables, one per model × quantization |
| `experiment_runner/csv_processor.ipynb`, `Results/EDA.ipynb` | Aggregation (median, IQR) and plots |
| `experiment_runner/quality_metrics/` | BERTScore and LLM-as-a-judge (G-Eval style) |
| `experiment_runner/quantization/` | imatrix + `IQ4_XS` quantization notebook |
| `experiment_runner/parser/` | Standalone log parsers for debugging |
| `plugins/BatteryManager/spy_app/` | On-device energy logger (BatteryManager companion APK) |
| `scrapers/` | Hugging Face GGUF model list and dataset downloader |
| `android-app/` | Early on-device chat/benchmark app prototype |
| `docs/REPRODUCE.md` | Reproduction guide |

## 🎓 Authors & Contact
**Eziyo Ehsani**
* MSc in Data Science, University of Naples Federico II
* [LinkedIn](https://www.linkedin.com/in/eziyo/)

**Co-Authors:** Luca Giamattei, Prof. Ivano Malavolta, Prof. Roberto Pietrantuono

## 📝 Citation
If you use this pipeline or our findings in your research, please consider citing our paper:
```bibtex
@article{ehsani2026sustainability,
  title={Sustainability Is Not Linear: Quantifying Performance, Energy, and Privacy Trade-offs in On-Device Intelligence},
  author={Ehsani, Eziyo and Malavolta, Ivano and Giamattei, Luca and Pietrantuono, Roberto},
  year={2026},
  institution={University of Naples Federico II & Vrije Universiteit Amsterdam}
}
```
Citation metadata is also available in [`CITATION.cff`](CITATION.cff).

## ⚖️ License
Released under the [MIT License](LICENSE). Third-party components (llama.cpp, Experiment-Runner, BatteryManager companion) keep their own licenses.