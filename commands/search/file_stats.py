COMMAND_NAME = "file_stats"
DESCRIPTION = (
    "Статистика файлов на компьютере: количество по категориям, "
    "что занимает больше всего места, поиск дубликатов."
)
PARAMETERS = {
    "query_type": {
        "type": "string",
        "description": "count — сколько файлов, largest — что занимает место, duplicates — дубликаты",
        "enum": ["count", "largest", "duplicates"],
    },
}
REQUIRED = ["query_type"]

_CAT_RU = {
    "document": "документов",
    "photo":    "фотографий",
    "video":    "видео файлов",
    "music":    "музыкальных файлов",
    "archive":  "архивов",
    "code":     "файлов кода",
    "other":    "прочих файлов",
}


def handler(query_type: str) -> str:
    from database.files.file_indexer import get_indexer

    indexer = get_indexer()

    if query_type == "count":
        stats = indexer.get_stats()
        total = stats["total_files"]
        if total == 0:
            return "Индекс пуст. Скажи «переиндексируй файлы»."

        parts = [f"Всего {total} файлов, занимают {stats['total_size']}."]
        for cat, data in sorted(stats["by_category"].items(), key=lambda x: -x[1]["count"]):
            ru = _CAT_RU.get(cat, cat)
            parts.append(f"{data['count']} {ru} ({data['size_human']}).")
        return " ".join(parts)

    if query_type == "largest":
        stats = indexer.get_stats()
        by_cat = stats["by_category"]
        if not by_cat:
            return "Индекс пуст."

        sorted_cats = sorted(
            by_cat.items(),
            key=lambda x: (
                indexer._conn.execute(
                    "SELECT SUM(size_bytes) FROM files WHERE category=?",
                    (x[0],)
                ).fetchone()[0] or 0
            ),
            reverse=True,
        )
        parts = ["Больше всего места занимают:"]
        for cat, data in sorted_cats[:4]:
            parts.append(f"{_CAT_RU.get(cat, cat)} — {data['size_human']}.")
        return " ".join(parts)

    if query_type == "duplicates":
        dups = indexer.find_duplicates(limit=5)
        if not dups:
            return "Дубликатов не найдено."

        parts = [f"Нашёл {len(dups)} групп дубликатов."]
        for d in dups[:3]:
            parts.append(
                f"Файл «{d['name']}» встречается {d['count']} раза, "
                f"каждый весит {d['size_human']}."
            )
        return " ".join(parts)

    return "Неизвестный тип запроса."