from database.supabase_client import supabase


def create_conversation(user_id, title):
    result = (
        supabase
        .table("conversations")
        .insert({
            "user_id": user_id,
            "title": title
        })
        .execute()
    )

    if result.data:
        print(f"[history] conversation created | id={result.data[0]['id']} | user_id={user_id}")
        return result.data[0]

    print(f"[history] conversation insert returned no data | user_id={user_id}")
    return None


def save_message(
    conversation_id,
    sender,
    content
):
    result = supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "sender": sender,
        "content": content
    }).execute()

    if result.data:
        print(
            f"[history] message saved | conversation_id={conversation_id} | sender={sender}"
        )
        return result.data[0]

    print(
        f"[history] message insert returned no data | conversation_id={conversation_id} | sender={sender}"
    )
    return None


def get_user_conversations(user_id):
    result = (
        supabase
        .table("conversations")
        .select("id,title,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    conversations = result.data or []
    print(f"[history] conversations fetched | user_id={user_id} | count={len(conversations)}")
    return conversations


def get_conversation_messages(conversation_id):
    result = (
        supabase
        .table("messages")
        .select("sender,content,created_at")
        .eq("conversation_id", conversation_id)
        .order("created_at")
        .execute()
    )

    messages = result.data or []
    print(
        f"[history] messages fetched | conversation_id={conversation_id} | count={len(messages)}"
    )
    return messages


def get_conversation(conversation_id):
    result = (
        supabase
        .table("conversations")
        .select("id,user_id,title,created_at")
        .eq("id", conversation_id)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]

    return None
