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

**Contents:** [Key findings](#-key-findings) · [How it works](#-how-it-works) · [Results at a glance](#-results-at-a-glance) · [Setup](#-setup-at-a-glance) · [Quick start](#-quick-start) · [Documentation](#-documentation) · [Repository structure](#-repository-structure) · [Citation](#-citation)

## 🚀 Key findings

These are the findings of one case study: one flagship phone, CPU-only `llama.cpp` inference and one single-turn summarization task.

- **Memory savings are not energy savings:** importance-aware `IQ4_XS` lowers peak memory compared with mixed-precision `Q4_K_M` (Q4_K_M uses 14.5 % more, median over all runs). It does not lower energy: Q4_K_M runs use 3.3 % less energy and have 4.9 % lower latency. All differences are statistically significant (Wilcoxon; effect sizes in `analysis/stat_tests.py`). The differences are small compared with the differences between models.
- **Model choice matters more than the 4-bit format:** across the eight models, energy and latency vary far more with model size and architecture than between the two quantizations.
- **One sparse model behaves like a small dense one:** the Mixture-of-Experts model OLMoE-1B-7B (≈1B active parameters per token) has the file size of a 7B model, but its speed and energy are in the range of the 1–2B dense models. Only one MoE model was evaluated.
- **Mid-sized models balance the trade-offs:** models around 3B parameters combine good quality with moderate latency and energy. Dense models of 7–9B need more than 10 s for a 100-token response on this device.
- **Metric bias:** reference-based BERTScore rewards small models that copy the input. A reference-free LLM judge (G-Eval style) better separates abstractive summaries.

## 🔧 How it works

```
 Computer (host)                                  Android phone (unrooted)
 ┌───────────────────────────────┐   Wi-Fi ADB    ┌──────────────────────────────────────┐
 │ Experiment-Runner             │ ─────────────► │ llama-cli (llama.cpp, CPU, 8 threads)│
 │  └ experiment/RunnerConfig.py │                │ <model>.gguf                         │
 │      ├ prompt + run control   │ ◄───────────── │ companion app: current, voltage,     │
 │      └ log_parsers.py         │   logs (pull)  │ temperature every 100 ms → logcat    │
 └───────────────────────────────┘                └──────────────────────────────────────┘
```

For every run:
1. The computer starts the battery logger on the phone.
2. It runs one summarization with `llama-cli` (exactly 100 tokens, greedy decoding).
3. It stops the logger, pulls both logs and turns them into one row of measurements: speed, latency, time to first token, memory, and energy as the baseline-subtracted, trapezoid-integrated power.
4. A 200 s cool-down follows.

Each configuration is repeated 30 times.

**Energy without root.** External power monitors require opening the phone, and low-level battery readings over ADB need root. Instead, a small companion app installed on the phone reads current and voltage through Android's official `BatteryManager` API. The phone stays unmodified and runs under realistic conditions, and the cable stays unplugged (wireless ADB) so charging can't distort the readings. Details and limits are in [`docs/METHODS.md`](docs/METHODS.md).

## 📊 Results at a glance

Median of 30 runs per configuration (from [`data/aggregated/final_results.csv`](data/aggregated/final_results.csv)). One 100-token summarization on the Galaxy S25 Ultra, CPU only. G-Eval is the LLM-judge quality score (0–1).

| Model | Decode speed (tok/s)<br>Q4_K_M / IQ4_XS | End-to-end latency (s)<br>Q4_K_M / IQ4_XS | Energy (J)<br>Q4_K_M / IQ4_XS | Peak memory (MiB)<br>Q4_K_M / IQ4_XS | G-Eval<br>Q4_K_M / IQ4_XS |
|---|---|---|---|---|---|
| Qwen2-0.5B | 50.5 / 56.2 | 2.53 / 2.29 | 44.0 / 36.8 | 678 / 632 | 0.52 / 0.50 |
| Qwen2.5-1.5B | 31.6 / 31.3 | 4.37 / 4.61 | 92.9 / 93.4 | 1373 / 1162 | 0.69 / 0.66 |
| Phi-2 (2.8B) | 21.4 / 20.8 | 7.15 / 7.35 | 143.8 / 142.0 | 1969 / 1712 | 0.68 / 0.64 |
| Qwen2.5-3B | 19.8 / 19.8 | 7.54 / 7.94 | 151.5 / 157.8 | 2320 / 1971 | 0.73 / 0.72 |
| OLMoE-1B-7B (MoE) | 38.2 / 38.5 | 3.60 / 3.74 | 76.5 / 79.0 | 4182 / 3707 | 0.60 / 0.58 |
| Qwen2.5-7B | 10.5 / 10.7 | 14.83 / 16.26 | 242.2 / 251.5 | 4792 / 4349 | 0.77 / 0.75 |
| Llama-3.1-8B | 10.5 / 9.1 | 16.13 / 18.68 | 291.7 / 302.5 | 5007 / 4556 | 0.73 / 0.71 |
| Gemma-2-9B | 7.2 / 6.8 | 20.15 / 22.06 | 316.3 / 325.2 | 6163 / 5612 | 0.92 / 0.91 |

Interquartile ranges, prefill speed, time to first token and the per-run data are in [`data/`](data/README.md).

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

This is only the outline. Before running on a phone, follow the **[step-by-step roadmap](docs/REPRODUCE.md#track-b-roadmap)**: building llama.cpp, preparing the models and the phone, and the 16 measurement rounds.

## 📚 Documentation

| Document | Read it to… |
|---|---|
| [`docs/REPRODUCE.md`](docs/REPRODUCE.md) | Reproduce the analysis (Track A) or run the whole experiment step by step (Track B): roadmap, checklists, how a round works, extending the study, troubleshooting |
| [`docs/METHODS.md`](docs/METHODS.md) | Understand the method: models and quantization (Q4_K_M, IQ4_XS, dense vs MoE), experimental controls and their reasons, workload and prompts, energy measurement (why, how, limits), quality evaluation (BERTScore, LLM judge), statistics |
| [`data/README.md`](data/README.md) | Use the data: files, every column with its unit, provenance |
| [`experiment/companion_app/README.md`](experiment/companion_app/README.md) | Learn about the on-device energy logger and its adaptations |
| [`archive/README.md`](archive/README.md) | See the early prototypes and why they were not used |

## 📂 Repository structure

```
├── experiment/          Measurement pipeline: RunnerConfig.py, log parsers, device helpers,
│                        companion app (energy logger), quantization notebook
├── analysis/            aggregate.py, stat_tests.py, reparse_raw_logs.py, figures.ipynb, quality/
├── data/                runs/ (480 runs), raw/ (raw logs), quality/, aggregated/  → see data/README.md
├── docs/                REPRODUCE.md (full guide), METHODS.md (methods in detail)
└── archive/             Early research prototypes (Android app, Perfetto, scrapers), not needed for the paper
```

## 🎓 Authors

**Eziyo Ehsani**¹ · **Ivano Malavolta**² · **Luca Giamattei**¹ · **Roberto Pietrantuono**¹

¹ University of Naples Federico II, Italy · ² Vrije Universiteit Amsterdam, The Netherlands

Contact: Eziyo Ehsani, [LinkedIn](https://www.linkedin.com/in/eziyo/). Questions and issues are welcome via [GitHub Issues](https://github.com/eziyoo/LLMs-on-Devices/issues).

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
