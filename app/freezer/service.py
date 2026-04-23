from dotenv import load_dotenv

from app.freezer.db_schema import FreezerSchemaMixin
from app.freezer.tableau_client import FreezerTableauMixin
from app.freezer.workflow import FreezerWorkflowMixin

load_dotenv()


class TableauFreezer(FreezerSchemaMixin, FreezerWorkflowMixin, FreezerTableauMixin):
    def __init__(self):
        self._tableau_server_url = None
        self._tableau_auth = None
        self._tableau_server = None
        self._init_db()
        try:
            self._init_tableau_client()
        except Exception as e:
            print(f"⚠️  [Tableau] Ошибка инициализации клиента: {e}")
