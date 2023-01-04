def split_list_in_chunks(items: list, limit: int) -> list[list]:
    return [items[i : i + limit] for i in range(0, len(items), limit)]
