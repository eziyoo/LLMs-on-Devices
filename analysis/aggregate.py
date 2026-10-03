"""Aggregate the per-run tables into one row per configuration (median, with IQR for the
speed, latency and energy metrics) and merge in the quality scores.

Inputs:  data/runs/*.csv, data/quality/bertscore_scores.csv, data/quality/llm_judge_scores.csv
Outputs: data/aggregated/final_results.csv and final_results.xlsx (read by analysis/figures.ipynb)

Usage:
    python analysis/aggregate.py
"""
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
RUNS_DIR = DATA_DIR / "runs"
QUALITY_DIR = DATA_DIR / "quality"
OUTPUT_DIR = DATA_DIR / "aggregated"

# GGUF file -> label used in the quality files and in the paper
MODEL_LABELS = {
    "qwen2-0_5b-instruct-q4_k_m.gguf":          "Qwen2-0.5B-Q4_K_M",
    "qwen2.5-1.5b-instruct-q4_k_m.gguf":        "Qwen2.5-1.5B-Q4_K_M",
    "phi-2.Q4_K_M.gguf":                        "Phi-2-2.8B-Q4_K_M",
    "qwen2.5-3b-instruct-q4_k_m.gguf":          "Qwen2.5-3B-Q4_K_M",
    "OLMoE-1B-7B-0125-Instruct-Q4_K_M.gguf":    "OLMoE-6.9B-Q4_K_M",
    "qwen2.5-7b-instruct-q4_k_m.gguf":          "Qwen2.5-7.6B-Q4_K_M",
    "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf":   "Llama3.1-8B-Q4_K_M",
    "gemma-2-9b-it-Q4_K_M.gguf":                "Gemma2-9B-Q4_K_M",
    "Qwen2-0.5b-instruct-iq4_xs.gguf":          "Qwen2-0.5B-IQ4_XS",
    "Qwen2.5-1.5B-Instruct-IQ4_XS.gguf":        "Qwen2.5-1.5B-IQ4_XS",
    "Phi-2-iq4_xs.gguf":                        "Phi-2-2.8B-IQ4_XS",
    "Qwen2.5-3B-Instruct-IQ4_XS.gguf":          "Qwen2.5-3B-IQ4_XS",
    "OLMoE-1B-7B-0125-Instruct-i1-IQ4_XS.gguf": "OLMoE-6.9B-IQ4_XS",
    "Qwen2.5-7B-Instruct-IQ4_XS.gguf":          "Qwen2.5-7.6B-IQ4_XS",
    "Meta-Llama-3.1-8B-Instruct-IQ4_XS.gguf":   "Llama3.1-8B-IQ4_XS",
    "gemma-2-9b-it-IQ4_XS.gguf":                "Gemma2-9B-IQ4_XS",
}

COLS_TO_MEDIAN = ['input_token_count', 'output_token_count',
                  'total_token_count', 'prompt_prefill_speed',
                  'generation_decoder_speed', 'prefill_latency',
                  'generation_latency', 'inference_latency',
                  'time_to_first_token', 'avg_current',
                  'avg_voltage', 'avg_power',
                  'total_energy_consumption', 'energy_per_token',
                  'average_temperature',
                  'peak_memory', 'model_weight', 'KV_cache',
                  'context_RAM', 'compute_RAM']

COLS_TO_IQR = ['prompt_prefill_speed', 'generation_decoder_speed',
               'prefill_latency', 'generation_latency',
               'inference_latency', 'time_to_first_token',
               'avg_power', 'total_energy_consumption', 'energy_per_token']

# Columns of the published final_results table
PUBLISHED_COLUMNS = ['model_name', 'prompt_prefill_speed', 'generation_decoder_speed',
                     'prefill_latency', 'generation_latency', 'inference_latency',
                     'time_to_first_token', 'total_energy_consumption', 'energy_per_token',
                     'battery_usage', 'average_temperature', 'peak_memory', 'model_weight',
                     'KV_cache', 'context_RAM', 'compute_RAM', 'Final_BERTscore', 'Overall_G-Eval']


# Values as published in the paper.
PAPER_VALUES = {
    ("Qwen2.5-7.6B-IQ4_XS", "total_energy_consumption"): 251.54,
}


def run_tables():
    """The 16 per-run tables, in run-ID order (1..16)."""
    files = sorted(RUNS_DIR.glob("*.csv"), key=lambda p: int(p.name.split("_")[0]))
    return [pd.read_csv(f) for f in files]


def aggregate(df):
    """One configuration -> one row: medians, 'median (IQR x)' strings and battery usage."""
    median_series = df[COLS_TO_MEDIAN].median().astype(object)

    iqr_series = df[COLS_TO_IQR].quantile(0.75) - df[COLS_TO_IQR].quantile(0.25)
    for col in COLS_TO_IQR:
        median_series[col] = f"{median_series[col]:.2f} (IQR {iqr_series[col]:.2f})"

    # Battery percentage used per run
    battery_val = (df['max_battery_capacity'].max() - df['min_battery_capacity'].min()) / 30

    row = median_series.copy()
    row['model_name'] = df['model_file'].iloc[0]
    row['battery_usage'] = battery_val
    return row


def main():
    final_df = pd.DataFrame([aggregate(df) for df in run_tables() if not df.empty])

    idx = COLS_TO_MEDIAN.index('energy_per_token') + 1
    final_df = final_df[['model_name'] + COLS_TO_MEDIAN[:idx] + ['battery_usage'] + COLS_TO_MEDIAN[idx:]]
    final_df['model_name'] = final_df['model_name'].map(MODEL_LABELS).fillna(final_df['model_name'])

    for (label, col), value in PAPER_VALUES.items():
        row = final_df['model_name'] == label
        iqr = final_df.loc[row, col].str.extract(r"(\(IQR [\d.]+\))", expand=False)
        final_df.loc[row, col] = f"{value:.2f} " + iqr

    bert = pd.read_csv(QUALITY_DIR / "bertscore_scores.csv")
    judge = pd.read_csv(QUALITY_DIR / "llm_judge_scores.csv")
    final_df['Final_BERTscore'] = final_df['model_name'].map(dict(zip(bert['model'], bert['BERT_F1'])))
    final_df['Overall_G-Eval'] = final_df['model_name'].map(dict(zip(judge['Model'], judge['Overall_Quality'])))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    final_df[PUBLISHED_COLUMNS].to_excel(OUTPUT_DIR / "final_results.xlsx", index=False)
    final_df.to_csv(OUTPUT_DIR / "final_results.csv", index=False)
    print(final_df[PUBLISHED_COLUMNS].to_string(index=False))
    print(f"\nSaved: {OUTPUT_DIR / 'final_results.xlsx'} and final_results.csv (all columns)")


if __name__ == "__main__":
    main()
