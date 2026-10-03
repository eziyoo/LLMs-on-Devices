# Archive

These are early prototypes from the exploratory phase of the research. They are **not needed to reproduce the paper**, and nothing in `experiment/` or `analysis/` depends on them. They are kept for transparency.

| Folder | What it is | Why it was not used |
|---|---|---|
| `android-app/` | Android chat and benchmark app built on a vendored copy of llama.cpp (JNI + Jetpack Compose) | The final experiment runs the `llama-cli` binary directly over ADB, so that measurements don't include app/UI overhead. |
| `perfetto/` | Perfetto trace config, a sample trace and a script that estimates CPU energy from frequency residency and a static power table | Static power models drift under thermal throttling. The paper measures battery current and voltage directly with the BatteryManager API instead. |
| `scrapers/` | Hugging Face GGUF model-list scraper (`fetch_models.py`) and a WikiText-2 / IMDb dataset downloader | Used to survey candidate models and calibration data. The final model selection is described in the paper. |
