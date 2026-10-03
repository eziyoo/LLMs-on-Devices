import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.stats import wilcoxon, friedmanchisquare
from statsmodels.stats.multitest import multipletests
import itertools
import sys

# ==========================================
# CONFIGURATION
# ==========================================
FILENAME = 'Total_Energy_Consumption.csv'
metric = FILENAME.removesuffix(".csv")
LOWER_IS_BETTER = True  # True for Energy/Time/Latency, False for Accuracy/Score/Speed

# ==========================================
# 1. LOAD DATA
# ==========================================
try:
    df = pd.read_csv(FILENAME)
    # The structure: First column is row labels (optional), rest are models
    # We assume the first column is an ID/Index and drop it for analysis
    data_matrix = df.iloc[:, 1:] 
    models = data_matrix.columns
    print(f"Loaded {len(models)} models: {list(models)}")
except FileNotFoundError:
    print(f"Error: '{FILENAME}' not found. Please check the file path.")
    sys.exit()

# ==========================================
# STEP A: FRIEDMAN OMNIBUS TEST
# ==========================================
stat_friedman, p_friedman = friedmanchisquare(*[data_matrix[col] for col in models])

print("\n" + "="*50)
print("       STEP 1: FRIEDMAN TEST (GLOBAL)")
print("="*50)
print(f"Friedman Chi-Square: {stat_friedman:.4f}")
print(f"P-Value:             {p_friedman:.4e}")

if p_friedman < 0.05:
    print(">> RESULT: SIGNIFICANT (Proceeding to Post-Hoc)")
else:
    print(">> RESULT: NOT SIGNIFICANT (Stop)")
    sys.exit()

# ==========================================
# STEP B: CALCULATE RANKS & SORT MODELS
# ==========================================
# If Lower is Better (Energy), we rank ascending (Smallest value = Rank 1)
# If Higher is Better (Accuracy), we rank descending (Largest value = Rank 1)
ranks = data_matrix.rank(axis=1, ascending=LOWER_IS_BETTER)

# Calculate mean rank for each model
mean_ranks = ranks.mean().sort_values() # Always sort 1 (Best) to N (Worst)
sorted_models = mean_ranks.index.tolist()

print("\n--- Model Ranking (Lower Mean Rank = Better) ---")
print(mean_ranks)

# ==========================================
# STEP C: PAIRWISE WILCOXON + HOLM (ALL PAIRS)
# ==========================================
p_values = []
pairs = []
stats = []

# Iterating through all unique pairs
for m1, m2 in itertools.combinations(models, 2):
    d1 = data_matrix[m1]
    d2 = data_matrix[m2]
    
    # Wilcoxon Test
    # Using method='auto' handles zero-differences correctly
    s, p = wilcoxon(d1, d2)
    
    # --- Manual Z-Score Calculation (Approximation) ---
    # 1. Calculate differences and effective N (excluding zero diffs)
    diffs = np.array(d1) - np.array(d2)
    n_eff = np.sum(diffs != 0)
    
    # 2. Compute Z only if n_eff is sufficient, else 0
    if n_eff > 0:
        mu = n_eff * (n_eff + 1) / 4
        sigma = np.sqrt(n_eff * (n_eff + 1) * (2 * n_eff + 1) / 24)
        z = (s - mu) / sigma
    else:
        z = 0
    
    p_values.append(p)
    pairs.append((m1, m2))
    stats.append(z)

# Apply Holm Correction
reject, p_corrected, _, _ = multipletests(p_values, alpha=0.05, method='holm')

# Create a lookup dictionary
p_lookup = {}
for i, (m1, m2) in enumerate(pairs):
    p_lookup[(m1, m2)] = (p_corrected[i], stats[i], reject[i])
    p_lookup[(m2, m1)] = (p_corrected[i], stats[i], reject[i])

# ==========================================
# STEP D: GENERATE THESIS TABLE (ADJACENT RANKS)
# ==========================================
thesis_data = []

print("\n" + "="*50)
print("       STEP 3: THESIS SUMMARY TABLE")
print("="*50)

for i in range(len(sorted_models)):
    model_curr = sorted_models[i]
    rank_curr = i + 1
    mean_rank = mean_ranks[model_curr]
    
    # Compare with the *next* ranked model in the sorted list
    if i < len(sorted_models) - 1:
        model_next = sorted_models[i+1]
        
        # Retrieve stats from lookup
        if (model_curr, model_next) in p_lookup:
            p_val, z_score, is_sig = p_lookup[(model_curr, model_next)]
        else:
            # Fallback if pair missing (shouldn't happen with itertools combinations)
            p_val, z_score, is_sig = 1.0, 0, False

        comp_str = f"vs. {model_next}"
        
        # Notation: *** < 0.001, ** < 0.01, * < 0.05
        if p_val < 0.001: sig_str = "***"
        elif p_val < 0.01: sig_str = "**"
        elif p_val < 0.05: sig_str = "*"
        else: sig_str = "ns"
        
        p_str = f"{p_val:.2e}"
        z_str = f"{z_score:.2f}"
    else:
        comp_str = "-"
        sig_str = "-"
        p_str = "-"
        z_str = "-"
    
    thesis_data.append([rank_curr, model_curr, f"{mean_rank:.2f}", comp_str, z_str, p_str, sig_str])

# Create DataFrame
df_thesis = pd.DataFrame(thesis_data, columns=[
    "Rank", "Model", "Mean Rank", "Comparison", "Z-Score", "Adj. P-Value", "Significance"
])

print(df_thesis.to_string(index=False))

# Save to CSV
#df_thesis.to_csv("thesis_table_results.csv", index=False)
#print("\n>> Saved table to 'thesis_table_results.csv'")

# ==========================================
# STEP E: PLOT HEATMAP (VISUAL PROOF)
# ==========================================
results_matrix = pd.DataFrame(index=models, columns=models, dtype=float)
np.fill_diagonal(results_matrix.values, 1.0) # Diagonal p-value is 1

for i, (m1, m2) in enumerate(pairs):
    p_val = p_corrected[i]
    results_matrix.loc[m1, m2] = p_val
    results_matrix.loc[m2, m1] = p_val

# Mask the upper triangle to avoid duplication
mask = np.triu(np.ones_like(results_matrix, dtype=bool))

plt.figure(figsize=(10, 8))
# Using 'Reds_r': Dark Red = Low P-value (Significant), Light/White = High P-value (Not Significant)
sns.heatmap(results_matrix, annot=True, fmt=".1e", 
            cmap="Reds_r", vmin=0, vmax=0.05, mask=mask,
            linewidths=0.5, linecolor='gray', cbar = False
            #cbar_kws={'label': 'Corrected P-Value (Darker = More Significant)'}
            )

plt.title(f'{metric}', fontsize=14)
plt.tight_layout()
plt.savefig(f'wilcoxon_heatmap_{metric}.png')
print(f">> Saved heatmap to 'wilcoxon_heatmap_{metric}.png'")