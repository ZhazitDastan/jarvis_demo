COMMAND_NAME = "rebuild_file_index"
DESCRIPTION = "Переиндексировать файлы — пересканировать все папки и обновить базу данных поиска."
PARAMETERS = {}
REQUIRED = []


def handler() -> str:
    from database.files.file_indexer import get_indexer
    import threading

    def _rebuild():
        get_indexer().build_index()

    threading.Thread(target=_rebuild, daemon=True).start()
    return "Переиндексация запущена в фоне. Обычно занимает 1-3 минуты."


