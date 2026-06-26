from database.supabase_client import supabase


def create_conversation(
    user_id,
    title
):
    result = (
        supabase
        .table("conversations")
        .insert({
            "user_id": user_id,
            "title": title
        })
        .execute()
    )

    return result.data[0]