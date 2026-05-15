# -*- coding: utf-8 -*-
import os

import vertica_python


class VerticaBackend:
    def connect(self):
        conn_info = {
            "host": os.getenv("VERTICA_HOST", "localhost"),
            "port": int(os.getenv("VERTICA_PORT", 5433)),
            "user": os.getenv("VERTICA_USER", "dbadmin"),
            "password": os.getenv("VERTICA_PASSWORD", ""),
            "database": os.getenv("VERTICA_DB", "docker"),
            "autocommit": True,
        }
        return vertica_python.connect(**conn_info)
