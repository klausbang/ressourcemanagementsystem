def _sort_key(value) -> str:
    return "" if value is None else str(value).lower()


def rows_with_meta(rows, dup_keys, sort_key=None, sort_dir="asc", sortable_keys=None):
    """Convert sqlite3.Row results into plain dicts, annotated for display.

    Adds a '_dup' bool flag marking rows whose dup_keys values are identical
    to another row's (a fully duplicated displayed line), and optionally
    sorts the rows by sort_key (only if it is present in sortable_keys).
    """
    items = [dict(r) for r in rows]

    if sort_key and sortable_keys and sort_key in sortable_keys:
        items.sort(key=lambda d: _sort_key(d.get(sort_key)), reverse=(sort_dir == "desc"))

    counts: dict[tuple, int] = {}
    row_dup_keys = []
    for item in items:
        key = tuple(_sort_key(item.get(k)) for k in dup_keys)
        row_dup_keys.append(key)
        counts[key] = counts.get(key, 0) + 1

    for item, key in zip(items, row_dup_keys):
        item["_dup"] = counts[key] > 1

    return items
