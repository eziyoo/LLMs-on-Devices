import pandas as pd
from scipy import stats

# 1. Load Data
df = pd.read_csv('run_table_all.csv')

# Clean column names (remove spaces like in 'quantization ')
df.columns = df.columns.str.strip()

# 2. Create Synthetic Repetition ID
df['rep_id'] = df.groupby(['model_file', 'quantization']).cumcount()

# 3. Create Paired Differences
df_pairs = df[df['quantization'].isin(['Q4_K_M', 'IQ4_XS'])].copy()

pivot = df_pairs.pivot_table(
    index=['model_file', 'rep_id'], 
    columns='quantization', 
    values='energy_per_token' # Change this to the metric you want to analyze
).dropna()

pivot['diff'] = pivot['Q4_K_M'] - pivot['IQ4_XS']

# 4. Run Shapiro-Wilk Test
if len(pivot['diff']) >= 3:
    stat, p_value = stats.shapiro(pivot['diff'])

    print(f"--- Shapiro-Wilk Test Results (Speed Differences) ---")
    print(f"Statistic: {stat:.4f}")
    print(f"p-value: {p_value:.4e}")