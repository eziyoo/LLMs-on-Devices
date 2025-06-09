
import pandas as pd
from huggingface_hub import HfApi, login

#api_token = "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"
#login(api_token)
api = HfApi()

models = list(api.list_models(library="gguf", sort='likes', direction=-1, limit=100))

#print(models[:5])  # Print the first 5 models for brevity

# Extract relevant info
data = []
for model in models:
    data.append({
        "model_id": model.id,
        "likes": model.likes or 0,
        "downloads": model.downloads or 0,
        "last_modified": model.lastModified,
        "tags": ", ".join(model.tags or [])
    })

# Convert to DataFrame
df = pd.DataFrame(data)

df.to_excel("top_models_filtered.xlsx", index=False)

print("Excel file 'top_models_filtered.xlsx' created.")