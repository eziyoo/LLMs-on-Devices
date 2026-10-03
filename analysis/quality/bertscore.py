"""Reference-based quality: BERTScore (roberta-large) of each evaluated response against a gold summary.

Input:  data/quality/evaluated_responses.csv
Output: data/quality/bertscore_scores.csv

Usage:
    python analysis/quality/bertscore.py
"""
from pathlib import Path

import pandas as pd
from bert_score import score

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "quality"
INPUT_FILE = DATA_DIR / "evaluated_responses.csv"
OUTPUT_FILE = DATA_DIR / "bertscore_scores.csv"

GOLD_SUMMARY = (
    "The World Wide Web was created by Tim Berners-Lee in 1989 at CERN to enable efficient information sharing among researchers, "
    "later evolving into a global information platform."
)


def main():
    df = pd.read_csv(INPUT_FILE)

    candidates = df["response"].tolist()
    references = [GOLD_SUMMARY] * len(candidates)

    print("Calculating BERTScore...")

    # Removed idf=True because calculating IDF on a single repeated reference
    # or small batch is statistically insignificant.
    P, R, F1 = score(
        candidates,
        references,
        lang="en",
        model_type="roberta-large",
        rescale_with_baseline=False,
        nthreads=1,
        verbose=True,
    )

    df["BERT_Precision"] = P.tolist()
    df["BERT_Recall"] = R.tolist()
    df["BERT_F1"] = F1.tolist()

    # Define the quality metric to avoid KeyError during sorting
    df["Final_Summary_Quality"] = df["BERT_F1"]

    final_df = df[[
        "model", "BERT_Precision", "BERT_Recall", "BERT_F1", "Final_Summary_Quality"
    ]].sort_values(by="Final_Summary_Quality", ascending=False)

    print("\n=== FINAL RESULTS ===")
    print(final_df.to_string(index=False))

    final_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
