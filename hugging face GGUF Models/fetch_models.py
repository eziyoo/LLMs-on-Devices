
from huggingface_hub import HfApi, login
import csv

#api_token = "***"
#login(api_token)

def fetch_models(library="gguf", sort="likes", direction=-1, limit=10):
    api = HfApi()
    all_models = []


    print("Fetching models...")
    
    models_iterator = api.list_models(
        library=library,
        direction = direction,
        sort=sort,
        limit=limit,
        )

    for model in models_iterator:
        all_models.append({
            "model": model.modelId,
            "likes": model.likes or 0,
            "downloads": model.downloads or 0,
            "tags": ", ".join(model.tags or [])
        })

    print(f"Fetched {len(all_models)} models.")
    return all_models

def save_to_csv(models, filename="excel/gguf_models.csv"):
    if not models:
        print("No models to save.")
        return

    with open(filename, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=models[0].keys())
        writer.writeheader()
        writer.writerows(models)

    print(f"Saved {len(models)} models to {filename}.")

if __name__ == "__main__":
    models = fetch_models()
    save_to_csv(models)
