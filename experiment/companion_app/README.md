# BatteryManager companion app

`com.example.batterymanager_utility.apk` is the on-device energy logger. It runs as a foreground service and reads battery current, voltage, capacity and temperature through the Android [`BatteryManager`](https://developer.android.com/reference/android/os/BatteryManager) API. Because it is a normal installed app, Android allows these readings without root or hardware modification. It prints one line per sample to logcat:

```
BatteryMgr:DataCollectionService: stats => <timestamp ms>,<current µA>,<voltage mV>,<capacity %>,<temperature 0.1 °C>
```

## How the experiment uses it

- **Install and permissions:** `python experiment/prepare_device.py` installs the APK, grants the notification permission (needed for a foreground service) and exempts the app from battery optimisation (otherwise Samsung's battery manager can kill the service).
- **Logging:** before every inference, `RunnerConfig.py` starts the service with `--ei sampleRate 100 --es dataFields "BATTERY_PROPERTY_CURRENT_NOW,EXTRA_VOLTAGE,BATTERY_PROPERTY_CAPACITY,EXTRA_TEMPERATURE" --ez toCSV False`, and stops it after the run.
- **Why logcat, not a CSV file:** with `toCSV False` the samples go straight to logcat instead of being buffered in the app's memory, so the logger doesn't compete with the LLM for RAM.

## Origin and adaptations for this study

The app is based on [S2-group/batterymanager-companion](https://github.com/S2-group/batterymanager-companion) (Vrije Universiteit Amsterdam). For this study it was cloned and adapted:
- **Build:** the Gradle configuration and Android API level were updated, so the app builds in current Android Studio and runs on Android 16.
- **Crash fix:** requesting a `BATTERY_*` property that the app does not map no longer crashes with a `NullPointerException`; the app logs an error and writes `0` in that field.

The adapted source is on [eziyoo/batterymanager-companion, branch `fix-battery-property-crash`](https://github.com/eziyoo/batterymanager-companion/tree/fix-battery-property-crash) (JDK 17). The APK in this folder is all you need to run the experiment.
