# Raw measurement logs

`raw_logs_ER2.zip` holds the raw per-run output of the final experiment round, the one reported in the paper. It has one folder per configuration:

```
experiments_<Q4_K_M|IQ4_XS>/<n>_<model>/results/s25_llama_thesis_experiment/
├── run_table.csv                 # Experiment-Runner table (same data as experiment_runner/csv/)
├── metadata.json
└── run_0_repetition_<0..29>/
    ├── llama_output.txt          # llama-cli -v output: timings, memory breakdown, response
    └── run_logcat.txt            # BatteryManager samples: ts(ms), current(µA), voltage(mV), capacity(%), temp(0.1 °C)
```

That is 16 configurations × 30 runs = 480 runs.

`run_logcat.txt` keeps only the `BatteryMgr:DataCollectionService: stats =>` lines. The original full logcat dumps also contained unrelated system logs with personal device data, so those lines were removed. They are exactly the lines the parsers read: re-parsing these files with `experiment_runner/parser/battery_parser.py` reproduces `total_energy_consumption` for all 480 runs.
