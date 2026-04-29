import sqlite3


class SQLiteCompatCursor:
    def __init__(self, cursor: sqlite3.Cursor, schema: str, dict_mode: bool = False):
        self._cursor = cursor
        self._schema = schema
        self._dict_mode = dict_mode
        self._last_write_rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._cursor.close()
        return False

    def _normalize_query(self, query: str) -> str:
        normalized = query.replace(f"{self._schema}.", "")
        normalized = normalized.replace(f"{self._schema.lower()}.", "")
        normalized = normalized.replace("{schema}.", "")
        normalized = normalized.replace("%s", "?")
        normalized = normalized.replace("LONG VARCHAR", "TEXT")
        return normalized

    def execute(self, query: str, params=None):
        normalized = self._normalize_query(query)
        write_stmt = normalized.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE"))
        if params is None:
            self._cursor.execute(normalized)
        else:
            self._cursor.execute(normalized, params)
        self._last_write_rowcount = 1 if write_stmt else 0
        return self

    def executemany(self, query: str, seq_of_params):
        normalized = self._normalize_query(query)
        params_list = list(seq_of_params)
        self._cursor.executemany(normalized, params_list)
        self._last_write_rowcount = len(params_list)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if self._dict_mode:
            return dict(row)
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        if self._dict_mode:
            return [dict(r) for r in rows]
        return rows

    @property
    def rowcount(self) -> int:
        rc = self._cursor.rowcount
        if rc == -1:
            return self._last_write_rowcount
        return rc


class SQLiteCompatConnection:
    def __init__(self, connection: sqlite3.Connection, schema: str):
        self._connection = connection
        self._schema = schema

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._connection.commit()
            else:
                self._connection.rollback()
        finally:
            self._connection.close()
        return False

    def cursor(self, mode=None):
        dict_mode = mode == "dict"
        return SQLiteCompatCursor(self._connection.cursor(), self._schema, dict_mode=dict_mode)


class SQLiteBackend:
    def __init__(self, schema: str, db_path: str):
        self._schema = schema
        self._db_path = db_path

    def connect(self):
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return SQLiteCompatConnection(connection, self._schema)
