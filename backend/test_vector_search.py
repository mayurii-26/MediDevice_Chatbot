from vector_store import search_products


query = input(
    "Ask Question: "
)

results = search_products(
    query
)

print("\nRESULTS:\n")

for i, result in enumerate(
    results,
    start=1
):

    print(
        f"\nResult {i}\n"
    )

    print(result)