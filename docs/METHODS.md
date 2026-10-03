# Methods in detail

This document records exactly how the published data were produced: the workload, the energy measurement, the quality evaluation and the statistics. It is a supplement to the paper's Methodology section. Every number below is computed from the published data in `data/`, and every setting is quoted from the code in this repository.

- [1. Workload](#1-workload)
- [2. Energy measurement](#2-energy-measurement)
- [3. Performance and memory metrics](#3-performance-and-memory-metrics)
- [4. Output quality](#4-output-quality)
- [5. Statistical analysis](#5-statistical-analysis)
- [6. Scope](#6-scope)

---

## 1. Workload

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

## 2. Energy measurement

**Instrument.** The BatteryManager companion app (`experiment/companion_app/`) runs as a foreground service on the phone. It reads `BATTERY_PROPERTY_CURRENT_NOW` (µA), `EXTRA_VOLTAGE` (mV), capacity (%) and temperature from the Android `BatteryManager` API and writes one timestamped line to logcat per sample. It needs no root and no hardware modification.

**Computation** (`experiment/log_parsers.py`, `parse_battery_log`):
1. For each sample, net current is |I| − I_baseline, floored at 0, with I_baseline = 0.10 A, the phone's idle current at minimum screen brightness.
2. Net power is P = net current × V.
3. Energy is E = Σ ½ (P_n + P_{n+1}) (t_{n+1} − t_n), the trapezoidal rule over all samples of the run.

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
- The method measures battery-level current, which includes everything else the phone does during the window; it is reduced by the baseline subtraction and the controls in `docs/REPRODUCE.md` §6.
- Absolute accuracy was not compared against an external power monitor in this study.
- The integrity of the processing can be checked: `python analysis/reparse_raw_logs.py` re-derives every published energy value from the raw samples.

---

## 3. Performance and memory metrics

All of them are parsed from the verbose output of `llama-cli` (`llama_output.txt`) by `experiment/log_parsers.py`:

- `prompt eval time` gives prefill latency, prompt tokens and prefill speed.
- `eval time` gives generation latency, generated tokens and decode speed.
- `total time` gives end-to-end inference latency.
- Time to first token = prefill latency + one decode step.
- The memory-breakdown line (`total = model + context + compute`) and `llama_kv_cache: size` give peak memory and its parts.

The full column list with units is in [`data/README.md`](../data/README.md); the parsing rules are in [`REPRODUCE.md`, Appendix B](REPRODUCE.md#b-how-each-metric-is-computed).

---

## 4. Output quality

Decoding is greedy, so all 30 runs of a configuration produce the same text. Because generation is forced to 100 tokens, models continue after their summary. The evaluated response is the summary itself: the generated text up to where the model begins an unrelated continuation, always a prefix of `model_response`. The 16 evaluated responses are in `data/quality/evaluated_responses.csv`, and both quality measures read that file.

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

## 5. Statistical analysis

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

## 6. Scope

The data come from one case study:
- one device (Samsung Galaxy S25 Ultra, Android 16);
- CPU-only inference with llama.cpp `llama-cli`;
- two 4-bit GGUF quantizations;
- eight models, one of them a Mixture-of-Experts model;
- one single-turn summarization task with a fixed 100-token output.

Results should be read within that scope. The pipeline is device-, model- and prompt-agnostic: see [Extending the study](REPRODUCE.md#extending-the-study) to run it on other phones, models or tasks.
