# Data

This folder holds all the data measured for the paper: 8 models × 2 quantizations = 16 configurations, 30 runs each (480 runs). Everything was recorded on a Samsung Galaxy S25 Ultra (Android 16) with the pipeline in `experiment/`.

```
data/
├── runs/                 # one table per configuration, one row per run (primary data)
├── raw/raw_logs.zip      # the raw logs behind every row in runs/
├── quality/              # responses that were scored + BERTScore and LLM-judge scores
└── aggregated/           # one row per configuration (medians), produced by analysis/aggregate.py
```

## `runs/`: per-run tables

Files are named by run ID `<n>_<model>_<quantization>.csv`:

| # | Q4_K_M | # | IQ4_XS | GGUF files |
|---|---|---|---|---|
| 1 | `1_qwen2-0_5b_Q4_K_M` | 9 | `9_qwen2-0_5b_IQ4_XS` | `qwen2-0_5b-instruct-q4_k_m.gguf` / `Qwen2-0.5b-instruct-iq4_xs.gguf` |
| 2 | `2_qwen2.5-1.5b_Q4_K_M` | 10 | `10_qwen2.5-1.5b_IQ4_XS` | `qwen2.5-1.5b-instruct-q4_k_m.gguf` / `Qwen2.5-1.5B-Instruct-IQ4_XS.gguf` |
| 3 | `3_phi-2_Q4_K_M` | 11 | `11_phi-2_IQ4_XS` | `phi-2.Q4_K_M.gguf` / `Phi-2-iq4_xs.gguf` |
| 4 | `4_qwen2.5-3b_Q4_K_M` | 12 | `12_qwen2.5-3b_IQ4_XS` | `qwen2.5-3b-instruct-q4_k_m.gguf` / `Qwen2.5-3B-Instruct-IQ4_XS.gguf` |
| 5 | `5_OLMoE_Q4_K_M` | 13 | `13_OLMoE_IQ4_XS` | `OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf` / `OLMoE-1B-7B-0125-Instruct-i1-IQ4_XS.gguf` |
| 6 | `6_qwen2.5-7b_Q4_K_M` | 14 | `14_qwen2.5-7b_IQ4_XS` | `qwen2.5-7b-instruct-q4_k_m.gguf` / `Qwen2.5-7B-Instruct-IQ4_XS.gguf` |
| 7 | `7_llama_Q4_K_M` | 15 | `15_llama_IQ4_XS` | `Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf` / `Meta-Llama-3.1-8B-Instruct-IQ4_XS.gguf` |
| 8 | `8_gemma_Q4_K_M` | 16 | `16_gemma_IQ4_XS` | `gemma-2-9b-it-Q4_K_M.gguf` / `gemma-2-9b-it-IQ4_XS.gguf` |

### Columns

| Column | Unit | Source / definition |
|---|---|---|
| `__run_id`, `__done` | n/a | Experiment-Runner bookkeeping (`run_0_repetition_<i>`, `DONE`) |
| `model_file` | n/a | GGUF file under test |
| `model_response` | text | Generated text (100 tokens, greedy decoding) |
| `input_token_count`, `output_token_count`, `total_token_count` | tokens | llama.cpp timing lines |
| `prompt_prefill_speed` | tokens/s | `prompt eval time` line |
| `generation_decoder_speed` | tokens/s | `eval time` line |
| `prefill_latency`, `generation_latency` | s | `prompt eval time`, `eval time` |
| `inference_latency` | s | `total time` (end to end) |
| `time_to_first_token` | s | prefill latency + one decode step |
| `avg_current` | A | Mean battery current, after subtracting the idle baseline (0.10 A) |
| `avg_voltage` | V | Mean battery voltage |
| `avg_power` | W | Mean of current × voltage per sample |
| `total_energy_consumption` | J | Trapezoidal integral of net power over the measurement window |
| `energy_per_token` | J/token | `total_energy_consumption / output_token_count` |
| `battery_capacity`, `min_battery_capacity`, `max_battery_capacity` | % | Battery level during the run |
| `average_temperature`, `min_temperature`, `max_temperature` | °C | Battery temperature |
| `peak_memory` | MiB | llama.cpp memory breakdown, total = model + context + compute |
| `model_weight`, `context_RAM`, `compute_RAM` | MiB | Parts of `peak_memory` |
| `KV_cache` | MiB | `llama_kv_cache: size` |

Battery samples are taken every 100 ms by the BatteryManager companion app. The parsing code is in `experiment/log_parsers.py`.

## `raw/raw_logs.zip`: raw logs

```
raw_logs/<run-id>/
├── run_table.csv                    # Experiment-Runner output (same rows as runs/<run-id>.csv)
├── metadata.json
└── run_0_repetition_<0..29>/
    ├── llama_output.txt             # verbose llama-cli output
    └── run_logcat.txt               # BatteryManager samples
```

- **Filtered logcat:** `run_logcat.txt` keeps only the `BatteryMgr:DataCollectionService: stats =>` lines. The original full logcat dumps also held unrelated system logs with personal device data. The parsers read only those lines.
- **Integrity check:** `python analysis/reparse_raw_logs.py` re-parses all 480 runs and reproduces every numeric value in `runs/`.
- **Missing response line:** in 9 logs llama-cli exited before printing its final `Parsed message` line, so the response text can't be re-extracted from the raw file there. Decoding is greedy, so each configuration has the same response in all 30 runs.

## `quality/`: output quality

| File | Content |
|---|---|
| `evaluated_responses.csv` | The response scored for each configuration (input of both quality scripts) |
| `bertscore_scores.csv` | BERTScore (roberta-large) precision, recall and F1 against a gold summary |
| `llm_judge_scores.csv` | LLM-as-a-judge (G-Eval style) scores: Coherence, Faithfulness, Relevance, Overall_Quality |

Every run generates exactly 100 tokens (`--ignore-eos`), so models keep writing after the summary. The scored response is the summary itself: the generated text up to where the model starts a new, unrelated continuation. It is always a prefix of the run's `model_response`.

## `aggregated/`: one row per configuration

`final_results.xlsx` (columns used by `analysis/figures.ipynb`) and `final_results.csv` (all columns) are produced by `python analysis/aggregate.py`:
- the median over the 30 runs;
- `"median (IQR x)"` strings for speed, latency and energy;
- `battery_usage` = battery percentage used per run;
- `Final_BERTscore` = BERT F1;
- `Overall_G-Eval` = the judge's Overall_Quality.
