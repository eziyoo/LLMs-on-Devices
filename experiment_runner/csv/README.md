# Per-run results

These are the final per-run tables used in the paper: one Experiment-Runner `run_table.csv` per configuration, 30 runs each. `csv_processor.ipynb` and the rebuild snippet in `docs/REPRODUCE.md` (section 16.3) read these exact names. The raw logs behind them are in `data/raw_logs_ER2.zip`.

| # | File | # | File |
|---|---|---|---|
| 1 | `1_qwen2-0_5b_Q4_K_M.csv` | 9 | `9_qwen2-0_5b_IQ4_XS.csv` |
| 2 | `2_qwen2.5-1.5b_Q4_K_M.csv` | 10 | `10_qwen2.5-1.5b_IQ4_XS.csv` |
| 3 | `3_phi-2_Q4_K_M.csv` | 11 | `11_phi-2_IQ4_XS.csv` |
| 4 | `4_qwen2.5-3b_Q4_K_M.csv` | 12 | `12_qwen2.5-3b_IQ4_XS.csv` |
| 5 | `5_OLMoE_Q4_K_M.csv` | 13 | `13_OLMoE_IQ4_XS.csv` |
| 6 | `6_qwen2.5-7b_Q4_K_M.csv` | 14 | `14_qwen2.5-7b_IQ4_XS.csv` |
| 7 | `7_llama_Q4_K_M.csv` | 15 | `15_llama_IQ4_XS.csv` |
| 8 | `8_gemma_Q4_K_M.csv` | 16 | `16_gemma_IQ4_XS.csv` |

Columns: `__run_id`, `__done`, `model_file`, `model_response`, then token counts, speeds, latencies, energy, battery, temperature and memory metrics (see `RunnerConfig.create_run_table_model`).
