import pandas as pd
from scipy import stats

# 1. LOAD DATA
try:
    df = pd.read_csv('run_table_all.csv')
    df.columns = df.columns.str.strip()
except FileNotFoundError:
    df = pd.DataFrame()

if not df.empty:
    df['Repetition'] = df.groupby(['model_file', 'quantization']).cumcount()
    df_clean = df[df['quantization'].isin(['Q4_K_M', 'IQ4_XS'])].copy()
else:
    df_clean = pd.DataFrame()

# 2. METRICS
metrics = {
    'generation_decoder_speed': {'Label': 'Generation Speed', 'Unit': 'tok/s', 'Goal': 'Higher is Better'},
    'total_energy_consumption': {'Label': 'Total Energy', 'Unit': 'J', 'Goal': 'Lower is Better'},
    'peak_memory': {'Label': 'Peak Memory', 'Unit': 'MB', 'Goal': 'Lower is Better'},
    'time_to_first_token': {'Label': 'Time to First Token', 'Unit': 's', 'Goal': 'Lower is Better'},
    'inference_latency': {'Label': 'Inference Latency', 'Unit': 's', 'Goal': 'Lower is Better'},
    'energy_per_token': {'Label': 'Energy per Token', 'Unit': 'J/tok', 'Goal': 'Lower is Better'}
}

results_table = []

# 3. ANALYZE
if not df_clean.empty:
    for col, info in metrics.items():
        pivot = df_clean.pivot_table(
            index=['model_file', 'Repetition'], 
            columns='quantization', 
            values=col
        ).dropna()
        
        if pivot.empty: continue

        # Calculate Differences (Q4 - IQ4)
        diff = pivot['Q4_K_M'] - pivot['IQ4_XS']
        diff_nz = diff[diff != 0] # Remove ties
        n = len(diff_nz)

        if n < 1: continue

        # Wilcoxon Test
        w_stat, p_value = stats.wilcoxon(diff_nz)

        results_table.append({
            'Metric': info['Label'],
            'W-Stat': f"{w_stat:.1f}",
            'p-value': f"{p_value:.2e}",
        })

results_df = pd.DataFrame(results_table)
print(results_df.to_markdown(index=False))