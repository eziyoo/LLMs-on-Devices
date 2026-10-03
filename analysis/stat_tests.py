"""Statistical tests reported in the paper, computed from the per-run tables in data/runs/.

1. Shapiro-Wilk normality of the paired (Q4_K_M - IQ4_XS) differences
2. Wilcoxon signed-rank test, Q4_K_M vs IQ4_XS (paired by model and repetition, zero differences dropped)
3. Friedman omnibus test across the 8 models, then pairwise Wilcoxon signed-rank tests with
   Holm-Bonferroni correction. Blocks = 30 Q4_K_M + 30 IQ4_XS repetitions per model.

Usage:
    python analysis/stat_tests.py [--heatmaps]
Tables are printed and saved to analysis/output/.
"""
import argparse
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

ROOT = Path(__file__).resolve().parents[1]
RUNS_DIR = ROOT / "data" / "runs"
OUTPUT_DIR = ROOT / "analysis" / "output"

# Run-ID model key -> model label (columns of the model-comparison matrices)
MODELS = {
    "qwen2-0_5b": "Qwen2-0.5B", "qwen2.5-1.5b": "Qwen2.5-1.5B", "phi-2": "Phi-2",
    "qwen2.5-3b": "Qwen2.5-3B", "OLMoE": "OLMoE-1B-7B", "qwen2.5-7b": "Qwen2.5-7B",
    "llama": "Llama-3.1-8B", "gemma": "Gemma-2-9B",
}
QUANTS = ["Q4_K_M", "IQ4_XS"]

# metric column -> (label, lower is better)
METRICS = {
    "generation_decoder_speed": ("Generation Speed", False),
    "total_energy_consumption": ("Energy Consumption", True),
    "peak_memory": ("Memory Usage", True),
    "inference_latency": ("Latency", True),
    "time_to_first_token": ("Time to First Token", True),
    "energy_per_token": ("Energy per Token", True),
}


def load_runs():
    """All 480 runs with model, quantization and repetition index."""
    frames = []
    for path in RUNS_DIR.glob("*.csv"):
        # run ID: <n>_<model key>_<quantization>, e.g. 10_qwen2.5-1.5b_IQ4_XS
        quant = next(q for q in QUANTS if path.stem.endswith("_" + q))
        key = path.stem.split("_", 1)[1][: -len(quant) - 1]
        df = pd.read_csv(path)
        df["model"] = MODELS[key]
        df["quantization"] = quant
        df["repetition"] = df["__run_id"].str.rsplit("_", n=1).str[-1].astype(int)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def paired_quantization_differences(runs, col):
    pivot = runs.pivot_table(index=["model", "repetition"], columns="quantization", values=col).dropna()
    return pivot["Q4_K_M"] - pivot["IQ4_XS"]


def model_matrix(runs, col):
    """60 x 8 block matrix: rows = quantization x repetition, columns = models."""
    matrix = runs.pivot_table(index=["quantization", "repetition"], columns="model", values=col)
    return matrix[list(MODELS.values())]


def quantization_tests(runs):
    rows = []
    for col, (label, _) in METRICS.items():
        diff = paired_quantization_differences(runs, col)
        w_sw, p_sw = stats.shapiro(diff)
        diff_nz = diff[diff != 0]  # Remove ties
        w, p = stats.wilcoxon(diff_nz)
        rows.append({"Metric": label, "Shapiro W": round(w_sw, 4), "Shapiro p": f"{p_sw:.4e}",
                     "Wilcoxon W": w, "Wilcoxon p": f"{p:.2e}",
                     "Median Q4_K_M - IQ4_XS": round(diff.median(), 4)})
    return pd.DataFrame(rows)


def model_comparison(runs, col, lower_is_better):
    data_matrix = model_matrix(runs, col)
    models = data_matrix.columns

    chi2, p_friedman = stats.friedmanchisquare(*[data_matrix[m] for m in models])
    mean_ranks = data_matrix.rank(axis=1, ascending=lower_is_better).mean().sort_values()

    pairs, p_values, z_scores = [], [], []
    for m1, m2 in itertools.combinations(models, 2):
        s, p = stats.wilcoxon(data_matrix[m1], data_matrix[m2])
        diffs = np.array(data_matrix[m1]) - np.array(data_matrix[m2])
        n_eff = np.sum(diffs != 0)
        if n_eff > 0:
            mu = n_eff * (n_eff + 1) / 4
            sigma = np.sqrt(n_eff * (n_eff + 1) * (2 * n_eff + 1) / 24)
            z = (s - mu) / sigma
        else:
            z = 0
        pairs.append((m1, m2))
        p_values.append(p)
        z_scores.append(z)
    reject, p_holm, _, _ = multipletests(p_values, alpha=0.05, method="holm")

    pairwise = pd.DataFrame({"model_a": [a for a, _ in pairs], "model_b": [b for _, b in pairs],
                             "z": z_scores, "p_raw": p_values, "p_holm": p_holm, "significant": reject})

    # Summary: each model against the next one in the ranking
    lookup = {frozenset((a, b)): (p, z) for a, b, p, z in zip(pairwise.model_a, pairwise.model_b, p_holm, z_scores)}
    ranked = mean_ranks.index.tolist()
    summary = []
    for i, model in enumerate(ranked):
        row = {"Rank": i + 1, "Model": model, "Mean Rank": round(mean_ranks[model], 2)}
        if i < len(ranked) - 1:
            p, z = lookup[frozenset((model, ranked[i + 1]))]
            sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else "ns"
            row.update({"vs. next": ranked[i + 1], "Z": round(z, 2), "Holm p": f"{p:.2e}", "Sig.": sig})
        summary.append(row)
    return chi2, p_friedman, pd.DataFrame(summary), pairwise


def save_heatmap(pairwise, models, title, path):
    import matplotlib.pyplot as plt
    import seaborn as sns

    matrix = pd.DataFrame(1.0, index=models, columns=models)
    for a, b, p in zip(pairwise.model_a, pairwise.model_b, pairwise.p_holm):
        matrix.loc[a, b] = matrix.loc[b, a] = p
    mask = np.triu(np.ones_like(matrix, dtype=bool))
    plt.figure(figsize=(10, 8))
    sns.heatmap(matrix, annot=True, fmt=".1e", cmap="Reds_r", vmin=0, vmax=0.05, mask=mask,
                linewidths=0.5, linecolor="gray", cbar=False)
    plt.title(title, fontsize=14)
    plt.tight_layout()
    plt.savefig(path)
    plt.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--heatmaps", action="store_true", help="also save Holm p-value heatmaps (PNG)")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    runs = load_runs()
    print(f"Loaded {len(runs)} runs from {RUNS_DIR}\n")

    quant = quantization_tests(runs)
    quant.to_csv(OUTPUT_DIR / "quantization_tests.csv", index=False)
    print("=== Q4_K_M vs IQ4_XS: Shapiro-Wilk (paired differences) and Wilcoxon signed-rank ===")
    print(quant.to_string(index=False))

    friedman_rows = []
    for col, (label, lower_is_better) in METRICS.items():
        chi2, p, summary, pairwise = model_comparison(runs, col, lower_is_better)
        friedman_rows.append({"Metric": label, "Friedman chi2": round(chi2, 2), "p": f"{p:.4e}"})
        summary.to_csv(OUTPUT_DIR / f"model_ranking_{col}.csv", index=False)
        pairwise.to_csv(OUTPUT_DIR / f"model_pairwise_{col}.csv", index=False)
        print(f"\n=== {label}: Friedman chi2 = {chi2:.2f}, p = {p:.4e} ===")
        print(summary.to_string(index=False))
        if args.heatmaps:
            save_heatmap(pairwise, list(MODELS.values()), label, OUTPUT_DIR / f"wilcoxon_holm_{col}.png")

    pd.DataFrame(friedman_rows).to_csv(OUTPUT_DIR / "friedman_tests.csv", index=False)
    print(f"\nSaved tables to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
