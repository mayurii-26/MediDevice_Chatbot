from vector_store import search_products
from gemini_service import generate_answer

question = input("Ask Question: ")

context = search_products(question)  # returns list[str] — pass directly

answer = generate_answer(question, context)

print("\n")
print(answer)
