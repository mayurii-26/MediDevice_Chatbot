from database.supabase_client import supabase

TABLE = "device_documents"


def get_categories() -> list[str]:
    result = (
        supabase.table(TABLE)
        .select("category")
        .eq("is_active", True)
        .execute()
    )
    seen = set()
    cats = []
    for row in result.data or []:
        c = row["category"]
        if c not in seen:
            seen.add(c)
            cats.append(c)
    return sorted(cats)


def get_subcategories(category: str) -> list[str]:
    result = (
        supabase.table(TABLE)
        .select("subcategory")
        .eq("category", category)
        .eq("is_active", True)
        .execute()
    )
    seen = set()
    subs = []
    for row in result.data or []:
        s = row["subcategory"]
        if s not in seen:
            seen.add(s)
            subs.append(s)
    return sorted(subs)


def get_documents(category: str, subcategory: str) -> list[dict]:
    result = (
        supabase.table(TABLE)
        .select("id, product_name, document_name, document_type, file_url")
        .eq("category", category)
        .eq("subcategory", subcategory)
        .eq("is_active", True)
        .order("product_name")
        .execute()
    )
    return result.data or []


def get_documents_by_product(product_name: str) -> list[dict]:
    result = (
        supabase.table(TABLE)
        .select("id, product_name, document_name, document_type, file_url, storage_path")
        .ilike("product_name", product_name)
        .eq("is_active", True)
        .order("document_name")
        .execute()
    )
    docs = result.data or []

    # Deduplicate by (document_name, document_type) — same PDF can appear
    # in multiple category rows with different storage_path / file_url
    seen: set[tuple] = set()
    unique: list[dict] = []
    for doc in docs:
        key = (doc.get("document_name", ""), doc.get("document_type", ""))
        if key not in seen:
            seen.add(key)
            unique.append(doc)
    docs = unique

    print(f"[documents] product={product_name} | found={len(docs)}")
    return docs
