"""Measure the phone's idle current, which is subtracted from every sample during the experiment.

Keep the phone in the same state as during the runs: screen on at minimum brightness, no
foreground app, unplugged, connected over wireless ADB. Do not touch it while this runs.

Usage:
    python experiment/measure_baseline.py --minutes 60
Then put the printed mean current into experiment/config.ini as baseline_current_a.
"""
import argparse
import statistics
import time

from settings import BATTERY_FIELDS, COMPANION_SERVICE, adb, load_settings

TAG = "BatteryMgr:DataCollectionService: stats =>"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--minutes", type=float, default=60, help="recording length (paper: 120)")
    parser.add_argument("--sample-rate", type=int, default=1000,
                        help="sampling interval in ms; the mean does not depend on it (default: %(default)s)")
    parser.add_argument("--save", default=None, help="optional path to save the raw samples")
    args = parser.parse_args()
    settings = load_settings()

    adb(settings, "logcat", "-G", "16M")
    adb(settings, "shell", "logcat", "-c")
    adb(settings, "shell", "settings", "put", "system", "screen_off_timeout", "2147483647")
    adb(settings, "shell", "am", "start-foreground-service", "-n", COMPANION_SERVICE,
        "--ei", "sampleRate", str(args.sample_rate), "--es", "dataFields", BATTERY_FIELDS, "--ez", "toCSV", "False")

    print(f"Recording idle current for {args.minutes:g} min. Leave the phone untouched...")
    try:
        time.sleep(args.minutes * 60)
    finally:
        adb(settings, "shell", "am", "stopservice", COMPANION_SERVICE)
        adb(settings, "shell", "settings", "put", "system", "screen_off_timeout", "120000")

    dump = adb(settings, "shell", "logcat", "-d", capture_output=True, text=True, errors="ignore").stdout
    lines = [line for line in dump.splitlines() if TAG in line]
    if args.save:
        with open(args.save, "w") as f:
            f.write("\n".join(lines) + "\n")

    amps, watts = [], []
    for line in lines:
        parts = line.split("stats => ")[1].strip().split(",")
        current_a, voltage_v = abs(int(parts[1])) / 1e6, int(parts[2]) / 1000
        amps.append(current_a)
        watts.append(current_a * voltage_v)

    if not amps:
        raise SystemExit("No samples found. Run experiment/prepare_device.py and try again.")
    print(f"samples={len(amps)}  mean current={statistics.mean(amps):.4f} A  mean power={statistics.mean(watts):.4f} W")
    print(f"Set in experiment/config.ini:  baseline_current_a = {statistics.mean(amps):.4f}")


if __name__ == "__main__":
    main()
