"""Run one short generation on the phone and check that llama-cli prints every line the
parsers need (timings, response, memory breakdown).

Usage:
    python experiment/sanity_check.py [--model qwen2-0_5b-instruct-q4_k_m.gguf]
"""
import argparse
import re
import sys

from settings import adb, load_settings

PROMPT = "Summarize the following text.\nText: The World Wide Web was invented in 1989 at CERN.\nOutput:"

REQUIRED_LINES = {
    "prefill timings (prompt eval time)": r"prompt eval time\s+=",
    "generation timings (eval time)": r"(?<!prompt)\s+eval time\s+=",
    "end-to-end latency (total time)": r"total time\s+=",
    "model response (Parsed message)": r"Parsed message: \{",
    "KV cache size (llama_kv_cache)": r"llama_kv_cache:\s+size\s+=",
    "memory breakdown (total = model + context + compute)": r"\d+\s+=\s+\d+\s+\+\s+\d+\s+\+\s+\d+",
}


def main():
    settings = load_settings()
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=settings.get("run", "model"),
                        help="GGUF file already in remote_dir on the phone (default: model from config.ini)")
    args = parser.parse_args()
    remote_dir = settings.get("device", "remote_dir", fallback="/data/local/tmp")

    cmd = (
        f"cd {remote_dir} && chmod +x llama-cli && "
        f"LD_LIBRARY_PATH=. ./llama-cli -m {args.model} -p '{PROMPT}' "
        f"-st -v -n 32 -c 512 -t 8 --temp 0 2>&1"
    )
    print(f"Running a 32-token generation with {args.model} ...")
    result = adb(settings, "shell", cmd, capture_output=True, text=True, errors="ignore")
    log = result.stdout

    missing = []
    for label, pattern in REQUIRED_LINES.items():
        found = re.search(pattern, log) is not None
        print(f"  [{'ok' if found else 'MISSING'}] {label}")
        if not found:
            missing.append(label)

    if missing:
        print("\nThe llama.cpp output format differs from what the parsers expect, or the run failed.")
        print("Last lines of the output:\n" + "\n".join(log.strip().splitlines()[-15:]))
        sys.exit(1)
    print("\nAll lines found. The device is ready for RunnerConfig.py.")


if __name__ == "__main__":
    main()
