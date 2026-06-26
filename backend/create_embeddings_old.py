import json
import pickle
import os
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

model = SentenceTransformer("all-MiniLM-L6-v2")

with open(
    os.path.join(BASE_DIR, "..", "data", "products_cleaned.json"),
    "r",
    encoding="utf-8",
) as f:
    products = json.load(f)

chunks = []

for product in products:
    text = (
        f"Product Name: {product['product_name']}\n"
        f"Category: {product['category']}\n"
        f"Description: {product['description']}\n"
    )

    if product.get("features"):
        text += "Features:\n"
        for feature in product["features"]:
            text += f"- {feature['title']}: {feature['description']}\n"

    if product.get("specifications"):
        text += "Specifications:\n"
        for key, value in product["specifications"].items():
            text += f"- {key}: {value}\n"

    chunks.append(text.strip())

print(f"Total Chunks: {len(chunks)}")

embeddings = model.encode(chunks, convert_to_numpy=True)
print("Embedding Shape:", embeddings.shape)

dimension = embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(np.array(embeddings, dtype=np.float32))

models_dir = os.path.join(BASE_DIR, "..", "models")
os.makedirs(models_dir, exist_ok=True)

faiss.write_index(index, os.path.join(models_dir, "faiss_index.bin"))

with open(os.path.join(models_dir, "product_chunks.pkl"), "wb") as f:
    pickle.dump(chunks, f)

print("FAISS index and product chunks saved successfully.")
