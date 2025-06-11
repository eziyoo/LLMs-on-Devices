
from huggingface_hub import HfApi, login
import csv, time

#api_token = "***"
#login(api_token)

def fetch_models(library="gguf", sort="likes", direction=-1):
    api = HfApi()
    all_models = []

    print("Fetching all models...")

    models_iterator = api.list_models(
        library=library,
        sort=sort,
        direction=direction,
        full=True,
        limit=1000
    )

    for i, model in enumerate(models_iterator, start=1):
        all_models.append({
            "model": model.id,
            "likes": model.likes or 0,
            "downloads": model.downloads or 0,
            "tags": ", ".join(model.tags or [])
        })

        """
        # Sleep after every 100 models
        if i % 10000 == 0:
            print(f"Fetched {i} models... sleeping for 5 seconds.")
            time.sleep(5)
        """

    print(f"Fetched {len(all_models)} models total.")
    return all_models


def clean_and_filter_models(models):
    cleaned_models = []

    for model in models:
        """
        tags = model.get("tags", "")
        tag_list = [tag.strip() for tag in tags.split(",")]

        # Only keep models with these tags
        if "reinforcement-learning" not in tag_list:
            cleaned_models.append(model)
        """
        # Make Model name better"
        model["model"] = model["model"].split("/", 1)[-1]
        cleaned_models.append(model)

    return cleaned_models

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
    models = fetch_models()  # Assume this returns a list of dicts
    filtered_models = clean_and_filter_models(models)
    save_to_csv(filtered_models)
