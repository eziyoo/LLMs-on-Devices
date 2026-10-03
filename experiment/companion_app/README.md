# BatteryManager companion app

`com.example.batterymanager_utility.apk` is the on-device energy logger. It runs as a foreground service and reads current, voltage, capacity and temperature through the Android [`BatteryManager`](https://developer.android.com/reference/android/os/BatteryManager) API, which needs no root. It prints one line per sample to logcat:

```
BatteryMgr:DataCollectionService: stats => <timestamp ms>,<current µA>,<voltage mV>,<capacity %>,<temperature 0.1 °C>
```

- **Source:** [S2-group/batterymanager-companion](https://github.com/S2-group/batterymanager-companion), with a fix for a `NullPointerException` on unmapped `BATTERY_*` properties. The patched source is at [eziyoo/batterymanager-companion, branch `fix-battery-property-crash`](https://github.com/eziyoo/batterymanager-companion/tree/fix-battery-property-crash) (JDK 17).
- **Install and permissions:** `python experiment/prepare_device.py` (see `docs/REPRODUCE.md` §8).
- **Control:** `RunnerConfig.py` starts it with `--ei sampleRate 100 --ez toCSV False` before every inference and stops it afterwards. Samples go to logcat, not the app's memory, so the logger doesn't compete with the LLM for RAM.
