"""Re-derive the published run tables from the raw logs and check that they match.

Extracts data/raw/raw_logs.zip, parses every run folder with experiment/log_parsers.py (the
same code RunnerConfig.py uses during the experiment) and compares each metric with
data/runs/<run-id>.csv.

In 9 of the 480 logs llama-cli exited before printing its final "Parsed message" line, so the
response text cannot be re-extracted there. Those are reported separately; every numeric metric is
checked for all runs. (Decoding is greedy, so each configuration has one response for all 30 runs.)

Usage:
    python analysis/reparse_raw_logs.py
"""
import csv
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiment"))
from log_parsers import DEFAULT_BASELINE_CURRENT_A, parse_run  # noqa: E402

RAW_ZIP = ROOT / "data" / "raw" / "raw_logs.zip"
RUNS_DIR = ROOT / "data" / "runs"
TOLERANCE = 1e-4  # some published values were re-saved with 5 decimals


def matches(published, parsed):
    if isinstance(parsed, str):
        return published.strip() == parsed.strip()
    return abs(float(published) - float(parsed)) <= TOLERANCE


def main():
    checked, mismatches, missing_responses = 0, [], 0
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(RAW_ZIP) as archive:
            archive.extractall(tmp)
        raw_root = Path(tmp) / "raw_logs"

        for table in sorted(RUNS_DIR.glob("*.csv"), key=lambda p: int(p.name.split("_")[0])):
            with open(table, newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                parsed = parse_run(raw_root / table.stem / row["__run_id"], DEFAULT_BASELINE_CURRENT_A, log=lambda *_: None)
                for column, value in parsed.items():
                    if column == "model_response":
                        missing_responses += not matches(row[column], value)
                    elif not matches(row[column], value):
                        mismatches.append((table.stem, row["__run_id"], column, row[column], value))
                checked += 1
            print(f"{table.stem:<24} {len(rows)} runs re-parsed")

    print(f"\n{checked} runs checked: {len(mismatches)} mismatching numeric values, "
          f"{missing_responses} logs without a re-extractable response")
    for m in mismatches[:20]:
        print("  ", m)
    sys.exit(1 if mismatches else 0)


if __name__ == "__main__":
    main()
