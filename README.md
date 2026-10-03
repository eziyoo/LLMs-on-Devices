<p align="center">
  <img src="docs/assets/app_icon.png" alt="LLMs on Devices" width="180">
</p>

<h1 align="center">🌱 Sustainability Is Not Linear</h1>

<p align="center">
  <b>Quantifying Performance, Energy, and Privacy Trade-offs in On-Device Intelligence</b><br>
  Replication package: pipeline, data and analysis
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue.svg" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/platform-Android%2016-green.svg" alt="Android 16">
  <img src="https://img.shields.io/badge/root-not%20required-lightgrey.svg" alt="No root required">
</p>

---

Running Large Language Models (LLMs) on a phone promises privacy, low latency and offline use, but it is limited by memory, thermal headroom and battery capacity. This repository contains a **reproducible, non-intrusive pipeline** that measures energy, latency, memory footprint and output quality of on-device LLMs on an **unrooted** Android phone, together with **all data and analysis** from the paper. It covers 8 open models from 0.5B to 9B parameters, each in 2 quantizations, with 30 runs per configuration.

## 🚀 Key findings

- **Quantization-energy paradox:** importance-aware quantization (`IQ4_XS`) reduces peak memory, but on CPU inference it does not reduce energy compared with mixed-precision `Q4_K_M`. `Q4_K_M` wins on speed, latency, time to first token and energy. The de-quantization overhead offsets the memory-bandwidth savings.
- **Architecture over parameter count:** model architecture and active compute per token predict energy and latency better than the 4-bit format does.
- **The promise of sparsity:** the Mixture-of-Experts model OLMoE-1B-7B has the storage footprint of a 7B model but the energy profile of a 1–2B dense model.
- **A practical sweet spot:** mid-sized models around 3B parameters balance quality, latency and energy. Dense models above 3B are too slow for interactive use.
- **Metric bias:** reference-based BERTScore rewards small models that copy the input. A reference-free LLM judge (G-Eval style) better reflects summary quality.

## 🧪 Setup at a glance

| | |
|---|---|
| **Device** | Samsung Galaxy S25 Ultra, Snapdragon 8 Elite, 12 GB RAM, Android 16 (unrooted) |
| **Inference** | `llama.cpp` `llama-cli`, CPU only, 8 threads, greedy decoding, 100 output tokens |
| **Models** | Qwen2-0.5B, Qwen2.5-1.5B, Phi-2, Qwen2.5-3B, OLMoE-1B-7B (MoE), Qwen2.5-7B, Llama-3.1-8B, Gemma-2-9B |
| **Quantization** | `Q4_K_M` (block-wise mixed precision) and `IQ4_XS` (importance-aware, codebook-based) |
| **Energy** | Android `BatteryManager` API at 100 ms via a companion app, baseline-subtracted, trapezoidal integration |
| **Orchestration** | [Experiment-Runner](https://github.com/S2-group/experiment-runner) over wireless ADB, 200 s cool-down between runs |
| **Quality** | BERTScore (reference-based) and LLM-as-a-judge (reference-free) |
| **Statistics** | Shapiro-Wilk, Wilcoxon signed-rank, Friedman + Holm-corrected pairwise Wilcoxon |

## ⚡ Quick start

**Reproduce the paper's analysis from the published data (no phone needed):**

```bash
git clone https://github.com/eziyoo/LLMs-on-Devices.git && cd LLMs-on-Devices
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python analysis/reparse_raw_logs.py     # optional: raw logs → per-run tables, integrity check
python analysis/aggregate.py            # per-run tables → one row per configuration
python analysis/stat_tests.py           # the paper's statistical tests
jupyter notebook analysis/figures.ipynb # figures
```

**Run the experiment on your own phone:**

```bash
cp experiment/config.example.ini experiment/config.ini   # device, paths, model under test
python experiment/prepare_device.py --brightness-min      # companion app + permissions
python experiment/sanity_check.py                         # llama.cpp output check
python experiment/measure_baseline.py --minutes 60        # idle current
python ../experiment-runner/experiment-runner/ experiment/RunnerConfig.py
```

📘 **The full step-by-step guide is in [`docs/REPRODUCE.md`](docs/REPRODUCE.md).** It covers requirements, building llama.cpp for Android, model quantization, phone preparation, running, analysis and troubleshooting.

## 📂 Repository structure

```
├── experiment/          Measurement pipeline: RunnerConfig.py, log parsers, device helpers,
│                        companion app (energy logger), quantization notebook
├── analysis/            aggregate.py, stat_tests.py, reparse_raw_logs.py, figures.ipynb, quality/
├── data/                runs/ (480 runs), raw/ (raw logs), quality/, aggregated/  → see data/README.md
├── docs/                REPRODUCE.md (full guide)
└── archive/             Early research prototypes (Android app, Perfetto, scrapers), not needed for the paper
```

## 🎓 Authors

**Eziyo Ehsani**¹ · **Ivano Malavolta**² · **Luca Giamattei**¹ · **Roberto Pietrantuono**¹

¹ University of Naples Federico II, Italy · ² Vrije Universiteit Amsterdam, The Netherlands

Contact: Eziyo Ehsani, [LinkedIn](https://www.linkedin.com/in/eziyo/)

## 📝 Citation

If you use this pipeline, data or findings, please cite:

```bibtex
@article{ehsani2026sustainability,
  title  = {Sustainability Is Not Linear: Quantifying Performance, Energy, and Privacy Trade-offs in On-Device Intelligence},
  author = {Ehsani, Eziyo and Malavolta, Ivano and Giamattei, Luca and Pietrantuono, Roberto},
  year   = {2026}
}
```

Citation metadata is also in [`CITATION.cff`](CITATION.cff).

## 🙏 Acknowledgements

This project has received funding from the European Union's Horizon 2020 research and innovation programme under the Marie Skłodowska-Curie grant agreement No 871342 "uDEVOPS". It builds on [llama.cpp](https://github.com/ggml-org/llama.cpp), [Experiment-Runner](https://github.com/S2-group/experiment-runner) and the [BatteryManager companion app](https://github.com/S2-group/batterymanager-companion).

## ⚖️ License

Released under the [MIT License](LICENSE). Third-party components keep their own licenses.
