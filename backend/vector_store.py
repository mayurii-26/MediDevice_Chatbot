import pickle
import faiss
import os
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "..", "models")

model = SentenceTransformer("all-MiniLM-L6-v2")

index = faiss.read_index(os.path.join(MODELS_DIR, "faiss_index.bin"))

with open(os.path.join(MODELS_DIR, "product_chunks.pkl"), "rb") as f:
    chunks = pickle.load(f)


def search_products(query: str, top_k: int = 3) -> list:
    query_embedding = model.encode([query])
    distances, indices = index.search(query_embedding, top_k)

    results = []
    for idx in indices[0]:
        if idx != -1 and idx < len(chunks):
            results.append(chunks[idx])

    return results
