"""Prepare the phone for measurements: install the BatteryManager companion app, grant its
permissions, exempt it from battery optimisation and enlarge the logcat buffer.

Usage:
    python experiment/prepare_device.py [--brightness-min]
"""
import argparse
import sys

from settings import COMPANION_PACKAGE, ROOT_DIR, adb, load_settings

APK = ROOT_DIR / "companion_app" / f"{COMPANION_PACKAGE}.apk"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--brightness-min", action="store_true",
                        help="also turn off adaptive brightness and set brightness to the minimum")
    args = parser.parse_args()
    settings = load_settings()

    if adb(settings, "get-state", capture_output=True, text=True).returncode != 0:
        sys.exit(f"Device {settings.get('device', 'device_id')} not reachable. Check `adb devices`.")

    steps = [
        ("Install companion app", ["install", "-r", "-g", str(APK)]),
        ("Grant notification permission", ["shell", "pm", "grant", COMPANION_PACKAGE, "android.permission.POST_NOTIFICATIONS"]),
        ("Exempt from battery optimisation", ["shell", "dumpsys", "deviceidle", "whitelist", f"+{COMPANION_PACKAGE}"]),
        ("Enlarge logcat buffer to 16 MB", ["logcat", "-G", "16M"]),
    ]
    if args.brightness_min:
        steps += [
            ("Disable adaptive brightness", ["shell", "settings", "put", "system", "screen_brightness_mode", "0"]),
            ("Set minimum brightness", ["shell", "settings", "put", "system", "screen_brightness", "1"]),
        ]

    for label, cmd in steps:
        result = adb(settings, *cmd, capture_output=True, text=True)
        status = "ok" if result.returncode == 0 else f"FAILED: {(result.stderr or result.stdout).strip()}"
        print(f"{label:<36} {status}")

    print("\nNext: python experiment/sanity_check.py")


if __name__ == "__main__":
    main()
