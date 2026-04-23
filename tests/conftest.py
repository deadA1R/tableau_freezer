import os


# Tests run without Vertica in local/dev environments.
os.environ.setdefault("FREEZER_DB_BACKEND", "sqlite")
os.environ.setdefault("FREEZER_SQLITE_PATH", "test_workflow_freeze.db")
