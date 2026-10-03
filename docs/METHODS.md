# Methods in detail

This document explains how the published data were produced and why the method looks the way it does. It covers the models and quantization formats, the experimental controls, the workload, the energy measurement, the quality evaluation and the statistics. It supplements the paper's Methodology section: numbers are computed from the published data in `data/`, and settings are quoted from the code in this repository. For the hands-on steps, see [`REPRODUCE.md`](REPRODUCE.md).

- [1. Models and quantization](#1-models-and-quantization)
- [2. Experimental controls](#2-experimental-controls)
- [3. Workload](#3-workload)
- [4. Energy measurement](#4-energy-measurement)
- [5. Performance and memory metrics](#5-performance-and-memory-metrics)
- [6. Output quality](#6-output-quality)
- [7. Statistical analysis](#7-statistical-analysis)
- [8. Scope](#8-scope)

---

## 1. Models and quantization

**Models.** Instruction-tuned models from 0.5B to 9B parameters. The selection took the highest-ranked open model per ≈1B-parameter band on the Hugging Face Open LLM Leaderboard. Below 0.5B, models lack the capacity for useful assistance; above 9B, they exceed the memory of current phones.

| Model | Parameters | Architecture | Hugging Face base |
|---|---|---|---|
| Qwen2-0.5B | 0.49B | Dense | `Qwen/Qwen2-0.5B-Instruct` |
| Qwen2.5-1.5B | 1.5B | Dense | `Qwen/Qwen2.5-1.5B-Instruct` |
| Phi-2 | 2.78B | Dense | `microsoft/phi-2` |
| Qwen2.5-3B | 3.09B | Dense | `Qwen/Qwen2.5-3B-Instruct` |
| OLMoE-1B-7B-0125 | 6.92B total, ≈1.3B active | Mixture-of-Experts | `allenai/OLMoE-1B-7B-0125-Instruct` |
| Qwen2.5-7B | 7.62B | Dense | `Qwen/Qwen2.5-7B-Instruct` |
| Llama-3.1-8B | 8.03B | Dense | `meta-llama/Llama-3.1-8B-Instruct` |
| Gemma-2-9B | 9.0B | Dense | `google/gemma-2-9b-it` |

**Dense vs. Mixture-of-Experts.**
- A dense model uses all of its parameters for every generated token: a 7B dense model reads all ≈7B weights for each token.
- A Mixture-of-Experts (MoE) model replaces each feed-forward block with many small "experts". A router sends each token to only a few of them. OLMoE-1B-7B has 64 experts per layer and activates 8 per token, so only ≈1.3B of its 6.9B parameters do work for any given token.
- **Consequences:**
  - compute per token is close to that of a ≈1B dense model;
  - all experts must still stay in memory, because the next token may need different ones, so peak memory is that of a 7B model.

  This is what the measurements show: OLMoE's speed and energy are close to the 1–2B dense models, while its memory footprint is close to the 7B ones. Only one MoE model was evaluated.

**Why 4-bit quantization.** A 7B model in 16-bit precision needs more than 14 GB of memory, which is more than a phone gives an app. Every model is therefore quantized to 4 bits, in two GGUF formats supported by llama.cpp:

- **`Q4_K_M`, block-wise mixed precision.** Weights are quantized in blocks. Most are stored at 4 bits, while the more sensitive tensors (parts of the attention and feed-forward layers) are kept at 6 bits. It is a common middle ground:
  - below 4 bits, block-wise quantization loses noticeable quality;
  - above 6 bits, the larger models no longer fit in phone memory.
- **`IQ4_XS`, importance-aware and codebook-based.** It is inspired by activation-aware quantization (AWQ), which showed that protecting a small fraction of important weights reduces quantization error.
  1. Calibration text (WikiText-2) is run through the FP16 model to build an *importance matrix*, which records how much each weight matters (`llama-imatrix`).
  2. Weights are not simply rounded. They are stored as indices into a shared *codebook* of representative values: important weights get values close to the originals, less important ones are compressed more.
  3. At inference time, the runtime looks up every index in the codebook to rebuild the weights.

  This gives a smaller memory footprint than `Q4_K_M` at similar quality, at the price of the lookup work during inference.

The commands are in [`REPRODUCE.md`, Phase 3](REPRODUCE.md#phase-3-prepare-the-models); the full IQ4_XS flow is in `experiment/quantization/quantize_iq4_xs.ipynb`.

---

## 2. Experimental controls

| Control | Setting | Why |
|---|---|---|
| Output length | Exactly 100 tokens (`-n 100 --ignore-eos`, end-of-turn token banned) | Energy grows with output length. If one model wrote 120 tokens and another 110, their energy would differ for that reason alone. |
| Input | One fixed text and instruction | The same work for every model. Tokenizers differ, so the prompt is 93–119 tokens depending on the model (§3). |
| Decoding | Temperature 0 (greedy), context 512 | Deterministic output: all 30 runs of a configuration produce the same text. |
| Threads | 8 CPU threads | All cores of the phone's CPU. |
| Repetitions | 30 per configuration | Stable distributions for energy and latency, which vary from run to run. |
| Warm-up | One untimed generation before the 30 runs | Removes cold-start effects (first model load, CPU frequency ramp-up). |
| Cool-down | 200 s between runs | Lets the phone return to its baseline temperature. In preliminary tests with different intervals, 200 s was enough to avoid thermal throttling carrying over between runs. |
| Screen | On, minimum brightness, timeout disabled during a round | When the screen turns off, Android assumes the phone is idle and throttles the CPU; in preliminary tests CPU power dropped by about half. |
| Background activity | Auto-sync, updates, radios, location off; Do Not Disturb; no open apps | Android regularly wakes background services (Google services, app updates, bug reports). Their CPU and battery use would add noise to the measurements. |
| Battery range | 80–100 %, one model per round, recharged between rounds | Battery voltage falls as charge drops (≈4.4 V when full). Keeping all rounds in the same range gives every model similar electrical conditions. |
| Connection | Wireless ADB through a separate hotspot | A USB cable would charge the phone and corrupt the discharge measurement. The phone's own hotspot would add radio power. |
| Log isolation | logcat cleared at the start of every run; previous output deleted on the phone | Each run's logs and outputs belong to that run only. |

---

## 3. Workload

**Task.** Single-turn summarization of one fixed paragraph. Every run sends the same text to the model:

> The World Wide Web (WWW) was invented by British scientist Tim Berners-Lee in 1989. He was working at CERN, the European Organization for Nuclear Research, near Geneva, Switzerland. Berners-Lee created the Web to meet the demand for automatic information-sharing between scientists in universities and institutes around the world.

The instruction is `Summarize the following text.`, wrapped in each model family's chat template (`experiment/RunnerConfig.py`, `interact()`):

| Models | Template | End-of-turn token(s) banned |
|---|---|---|
| Qwen2, Qwen2.5 | `<\|im_start\|>user\nSummarize the following text.\nText: {text}\n<\|im_end\|>\n<\|im_start\|>assistant\n` | 151643, 151645 |
| Phi-2 | `Summarize the following text.\n{text}\nOutput:` | 50256 |
| OLMoE | `<\|endoftext\|><\|user\|>\nSummarize the following text.\nText: {text}\n<\|assistant\|>\n` | 50279 |
| Llama-3.1 | `<\|begin_of_text\|><\|start_header_id\|>user<\|end_header_id\|>\n\nSummarize the following text.\nText: {text}<\|eot_id\|><\|start_header_id\|>assistant<\|end_header_id\|>\n\n` | 128009 |
| Gemma-2 | `<start_of_turn>user\nSummarize the following text.\nText: {text}<end_of_turn>\n<start_of_turn>model\n` | 107 |

**Generation settings** (identical for every run): `llama-cli -st -v -n 100 --ignore-eos --logit-bias <eos>-inf -c 512 -t 8 --temp 0`.
- Exactly 100 output tokens per run: end-of-generation is disabled and the end-of-turn token is banned.
- Greedy decoding (temperature 0), a 512-token context and 8 CPU threads.

**Isolation between runs.** Each run starts a new `llama-cli` process (`-st`, single turn). Nothing carries over from one run to the next: no KV cache, no prompt cache and no conversation state. The model file stays in the phone's storage. One warm-up generation with the same model precedes the 30 runs of a configuration.

**Prompt length** (from `input_token_count`; constant across the 30 runs of a configuration):

| Model | Q4_K_M | IQ4_XS |
|---|---|---|
| Qwen2-0.5B | 103 | 103 |
| Qwen2.5-1.5B | 113 | 113 |
| Phi-2 | 108 | 105 |
| Qwen2.5-3B | 113 | 113 |
| OLMoE-1B-7B | 102 | 102 |
| Qwen2.5-7B | 103 | 113 |
| Llama-3.1-8B | 119 | 119 |
| Gemma-2-9B | 93 | 93 |

---

## 4. Energy measurement

**Why this approach.** Three ways to measure phone energy were considered:

| Approach | Why it was not used |
|---|---|
| External power monitor (e.g. Monsoon) | The most accurate, but the phone must be opened and its battery bypassed. This alters its thermal behaviour, voids the warranty and makes the setup hard for others to replicate. |
| Software power models (Perfetto CPU-frequency traces × a power table) | Tried in a prototype (`archive/perfetto/`). Small changes in workload or temperature shift CPU frequencies, so the estimates were unstable during long LLM runs. |
| Reading current and voltage over ADB | Modern Android blocks these low-level readings for non-privileged users. Getting them would need root, which changes the operating system and its power management. |

The chosen approach is a **companion app** installed on the phone as a normal app. Android lets installed apps read battery current, voltage and temperature through the official `BatteryManager` API, so it works on an unmodified, unrooted phone under realistic conditions. The trade-off is lower time resolution than an external monitor (see *Sampling* below).

**Instrument.** The BatteryManager companion app (`experiment/companion_app/`) runs as a foreground service on the phone. It reads `BATTERY_PROPERTY_CURRENT_NOW` (µA), `EXTRA_VOLTAGE` (mV), capacity (%) and temperature from the Android `BatteryManager` API and writes one timestamped line to logcat per sample. It needs no root and no hardware modification.

**Computation** (`experiment/log_parsers.py`, `parse_battery_log`):
1. For each sample, net current is |I| − I_baseline, floored at 0, with I_baseline = 0.10 A, the phone's idle current at minimum screen brightness.
2. Net power is P = net current × V.
3. Energy is E = Σ ½ (P_n + P_{n+1}) (t_{n+1} − t_n), the trapezoidal rule over all samples of the run.

*Why integrate instead of averaging?* Power is not constant during a run: it is low while the model loads and high during decoding. Multiplying one average power by the total time can be misleading, just as a trip of one hour standing still and one hour at 100 km/h has an "average speed" of 50 km/h. The trapezoidal rule handles each pair of consecutive samples separately: it takes their mean power and multiplies it by the time between them, then adds up all these slices.

**Sampling, measured on the 480 published runs** (`data/raw/raw_logs.zip`):

| Quantity | Value |
|---|---|
| Requested sampling interval | 100 ms |
| Observed interval between logged samples | median 101 ms, 95th percentile 107 ms |
| Interval between changes of the current reading | median ≈ 310 ms; 71 % of consecutive samples repeat the previous value |
| Samples per run | 49–273 (median 104) |
| Measurement window per run | 4.9–27.7 s (median 10.5 s) |
| Inference latency per run (`inference_latency`) | 2.3–22.9 s |

- **Effective resolution:** the phone's fuel gauge refreshes the current about every 300 ms, so the effective time resolution is ≈ 3 Hz. Logging at 100 ms makes sure every refresh is captured.
- **Shortest run:** even the shortest inference (2.3 s) spans about 7 independent current readings, and the shortest measurement window spans about 15.
- **Spikes:** power changes shorter than the fuel-gauge refresh are averaged by the hardware and cannot be resolved with this method.

**Measurement window.** The service starts 2 s before `llama-cli` is launched and is stopped after the run's output has been pulled. The window therefore covers:
- the 2 s spin-up;
- the whole `llama-cli` process (model loading, prefill, decoding, exit);
- the ADB commands around it.

All of it is net of the idle baseline.

**Clocks.** All timestamps used in the energy integral come from one clock, the phone's `System.currentTimeMillis()`, written by the companion app. Latencies come from llama.cpp's internal timers on the phone. The host computer's clock is never used in any computation, so no host–device clock synchronisation is involved.

**Limits.**
- The method measures battery-level current, which includes everything else the phone does during the window; it is reduced by the baseline subtraction and the controls in §2.
- Absolute accuracy was not compared against an external power monitor in this study.
- The integrity of the processing can be checked: `python analysis/reparse_raw_logs.py` re-derives every published energy value from the raw samples.

---

## 5. Performance and memory metrics

All of them are parsed from the verbose output of `llama-cli` (`llama_output.txt`) by `experiment/log_parsers.py`:

- `prompt eval time` gives prefill latency, prompt tokens and prefill speed.
- `eval time` gives generation latency, generated tokens and decode speed.
- `total time` gives end-to-end inference latency.
- Time to first token = prefill latency + one decode step.
- The memory-breakdown line (`total = model + context + compute`) and `llama_kv_cache: size` give peak memory and its parts.

The full column list with units is in [`data/README.md`](../data/README.md); the parsing rules are in [`REPRODUCE.md`, Appendix A](REPRODUCE.md#a-how-each-metric-is-computed).

---

## 6. Output quality

Decoding is greedy, so all 30 runs of a configuration produce the same text. Because generation is forced to 100 tokens, models continue after their summary. The evaluated response is the summary itself: the generated text up to where the model begins an unrelated continuation, always a prefix of `model_response`. The 16 evaluated responses are in `data/quality/evaluated_responses.csv`, and both quality measures read that file.

**Why two quality measures.**
- **BERTScore** compares each response with a human-written reference summary using contextual embeddings, so different wording with the same meaning still scores well.
- **The LLM judge** scores each response without a reference, on faithfulness, relevance and coherence. In this study the judge proved necessary, for two reasons:
  - Small models often copied large parts of the source text with minor edits. Because the copy is semantically close to the reference, BERTScore rated them highly, sometimes higher than larger models.
  - Larger models paraphrased and restructured the text into real summaries. These diverged more from the reference wording and sometimes scored lower.

  BERTScore therefore favoured extractive copying over abstractive summarization. The paper reports both measures and relies on the judge for summary quality.

### BERTScore (reference-based), `analysis/quality/bertscore.py`

- `bert_score.score(..., lang="en", model_type="roberta-large", rescale_with_baseline=False)`, no IDF weighting.
- Reference: one gold summary for all candidates: *"The World Wide Web was created by Tim Berners-Lee in 1989 at CERN to enable efficient information sharing among researchers, later evolving into a global information platform."*
- Reported value: F1 (`Final_BERTscore`).

### LLM-as-a-judge (reference-free, G-Eval style), `analysis/quality/llm_judge.py`

| Setting | Value |
|---|---|
| Judge model | OpenAI `gpt-5.2` |
| Decoding | `temperature=0`, `seed=42`, structured output (a list of `{model_id, score}`) |
| Criteria | Faithfulness, Relevance, Coherence, Overall_Quality: one judge call per criterion |
| Scoring | Comparative: each call contains the source text and all 16 responses, and the judge scores each response from 0.00 to 1.00 relative to the others |
| Blinding | Responses are labelled only `MODEL ID: <n>`; model names and quantization are never shown to the judge |
| Order | Fixed (IDs 1–16: the 8 Q4_K_M configurations, then the 8 IQ4_XS ones) |
| Repetitions | 1 call per criterion |
| Reported value | `Overall_G-Eval` = the score of the Overall_Quality criterion; it is a separate criterion, not an average of the other three |

<details>
<summary>Prompt and evaluation steps (verbatim)</summary>

System prompt, sent once per criterion:

```
You are an expert evaluator grading AI summaries on the metric: <CRITERION>.

EVALUATION STEPS:
- <steps of the criterion, below>

INSTRUCTIONS:
1. Read the SOURCE CONTEXT.
2. Read all MODEL CANDIDATES (identified by ID).
3. Compare the candidates AGAINST EACH OTHER based on the Evaluation Steps.
4. Assign a score (0.00 - 1.00). The best model relative to the others should get the highest score.
5. Be strict. If a model hallucinates, give it a low score on Consistency.
```

User prompt: `SOURCE CONTEXT:\n<source text>\n\nCANDIDATES:\n--- MODEL ID: 1 ---\n<response>\n\n--- MODEL ID: 2 --- …`

**Faithfulness**
- Extract all specific claims, dates, and entities made in the 'Actual Output'.
- Cross-reference each extracted claim against the 'Input' (Source Text).
- CRITICAL: Identify any information in the output that contradicts the source or appears to be hallucinated (unsupported).
- High score ONLY if every fact is verifiable in the source text.
- Low score if the model invents major facts not present in the source.
- Output an overall model faithfulness score between 0.00 and 1.00.

**Relevance**
- Analyze the 'Input' text and list the core information units (key entities like 'Tim Berners-Lee', actions, dates like '1989').
- Check the 'Actual Output' to see which of these core information units are present.
- Identify any critical concepts from the source that were omitted in the summary.
- High score if the summary provides a comprehensive overview of the source text's main message.
- Low score if the summary misses the main topic entirely.
- Output an overall model relevancy score between 0.00 and 1.00.

**Coherence**
- Read the 'Actual Output' and analyze the logical progression of ideas.
- Check for smooth transitions between sentences and clauses (e.g., proper use of connectives).
- Scan specifically for 'Repetition Loops' (repeating the same phrase) or cut-off sentences.
- Ensure pronouns and references (e.g., 'he', 'it') clearly point to the correct entities.
- High score for perfect, natural English flow.
- Low score for disjointed lists, word salad, or severe grammatical errors.
- Output an overall model coherence score between 0.00 and 1.00.

**Overall_Quality**
- Holistically evaluate the summary's utility.
- IMMEDIATE FAIL: If the response is a copy-paste of the source (or >80 percent similarity), the MAXIMUM score is 0.20.
- Check for 'lazy' summarization: Does the model just delete a few adjectives but keep the exact sentence structure?
- Look for 'synthesis': Did the model combine multiple source sentences into one new, efficient sentence?
- Reward models that use their own vocabulary to convey the full meaning in significantly fewer words.
- High score for excellent, high-compression summarization.
- Output an overall model quality score between 0.00 and 1.00.

</details>

The scores are in `data/quality/llm_judge_scores.csv` (all four criteria) and `data/quality/bertscore_scores.csv` (precision, recall, F1).

---

## 7. Statistical analysis

Run `python analysis/stat_tests.py`. All tests use the per-run tables in `data/runs/`.

- **Unit of analysis.** One run, which is one independent execution of `llama-cli`. There are 30 runs per configuration and 480 in total.
- **Pairing.** Runs are paired by repetition index (run *i* of one configuration with run *i* of another). Configurations were measured in separate rounds, so the pairing reflects run order within a round, not a shared physical condition.
- **Normality.** Shapiro-Wilk on the paired differences Q4_K_M − IQ4_XS (240 pairs per metric).
- **Quantization.** Wilcoxon signed-rank test, Q4_K_M vs IQ4_XS, on the same 240 pairs; zero differences are dropped.
- **Models.** Friedman test across the 8 models, with 60 blocks per model (30 Q4_K_M + 30 IQ4_XS repetitions). Then all 28 pairwise Wilcoxon signed-rank tests with Holm-Bonferroni correction, and mean ranks (1 = best).
- **Effect sizes.**
  - The matched-pairs rank-biserial correlation *r* for every Wilcoxon test: *r* = (T₊ − T₋)/(T₊ + T₋), from −1 to 1, and |*r*| = 1 when every pair differs in the same direction.
  - For Q4_K_M vs IQ4_XS, also the median paired difference and the relative difference of the medians.

Output: printed tables plus `analysis/output/quantization_tests.csv`, `friedman_tests.csv`, `model_ranking_<metric>.csv` and `model_pairwise_<metric>.csv`.

---

## 8. Scope

The data come from one case study:
- one device (Samsung Galaxy S25 Ultra, Android 16);
- CPU-only inference with llama.cpp `llama-cli`;
- two 4-bit GGUF quantizations;
- eight models, one of them a Mixture-of-Experts model;
- one single-turn summarization task with a fixed 100-token output.

Results should be read within that scope. The pipeline is device-, model- and prompt-agnostic: see [Extending the study](REPRODUCE.md#extending-the-study) to run it on other phones, models or tasks.
