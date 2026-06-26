"""
vector_db/create_embeddings.py
Reads all category products.json files, builds FAISS index,
and saves faiss_index.bin + product_chunks.pkl into vector_db/
"""
import json
import pickle
import os
import glob
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

model = SentenceTransformer("all-MiniLM-L6-v2")

# Load all products from every category folder
all_products = []
category_files = glob.glob(os.path.join(DATA_DIR, "**", "products.json"), recursive=True)

for filepath in category_files:
    with open(filepath, "r", encoding="utf-8") as f:
        products = json.load(f)
        all_products.extend(products)
    print(f"Loaded {len(products)} products from {filepath}")

print(f"\nTotal products: {len(all_products)}")

# Build text chunks
chunks = []
for product in all_products:
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

print(f"Total chunks: {len(chunks)}")

if not chunks:
    print("No chunks to embed. Add products to data/ category folders first.")
    exit(0)

# Embed
embeddings = model.encode(chunks, convert_to_numpy=True, show_progress_bar=True)
print("Embedding shape:", embeddings.shape)

# Build FAISS index
dimension = embeddings.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(np.array(embeddings, dtype=np.float32))

# Save
faiss.write_index(index, os.path.join(BASE_DIR, "faiss_index.bin"))
with open(os.path.join(BASE_DIR, "product_chunks.pkl"), "wb") as f:
    pickle.dump(chunks, f)

print("faiss_index.bin and product_chunks.pkl saved to vector_db/")
