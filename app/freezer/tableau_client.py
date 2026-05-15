# -*- coding: utf-8 -*-
import io
import os
from urllib.parse import unquote

import tableauserverclient as TSC
import urllib3
import urllib3.exceptions


class FreezerTableauMixin:
    def _init_tableau_client(self):
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        self._tableau_server_url = os.getenv("TABLEAU_SERVER_URL")
        token_name = os.getenv("TABLEAU_TOKEN_NAME")
        token_value = os.getenv("TABLEAU_TOKEN_VALUE")
        site_id = os.getenv("TABLEAU_SITENAME", "")

        if all([self._tableau_server_url, token_name, token_value]):
            self._tableau_auth = TSC.PersonalAccessTokenAuth(
                token_name=token_name,
                personal_access_token=token_value,
                site_id=site_id,
            )
            self._tableau_server = TSC.Server(self._tableau_server_url, use_server_version=True)
            self._tableau_server.add_http_options({"verify": False})
            print("? [Tableau] Клиент инициализирован")
        else:
            self._tableau_auth = None
            self._tableau_server = None
            print("??  [Tableau] Credentials не заданы — выгрузка из Tableau недоступна")

    def get_view_data(self, workbook_name_or_path: str, parameters: dict = None):
        import pandas as pd
        import requests

        if self._tableau_server is None or self._tableau_auth is None:
            raise RuntimeError("Tableau credentials не заданы в .env")

        with self._tableau_server.auth.sign_in(self._tableau_auth):
            print(f"[Tableau] Ищу: {repr(workbook_name_or_path)}")

            target_sheet_name = None
            search_name = workbook_name_or_path

            if "/" in workbook_name_or_path:
                parts = unquote(workbook_name_or_path).replace("views/", "").split("/")
                search_name = parts[0]
                target_sheet_name = parts[-1].split("?")[0]
                print(f"[Tableau]   Воркбук: {repr(search_name)}")
                print(f"[Tableau]   Лист:    {repr(target_sheet_name)}")

            req_options = TSC.RequestOptions()
            req_options.filter.add(
                TSC.Filter(
                    TSC.RequestOptions.Field.Name,
                    TSC.RequestOptions.Operator.Equals,
                    search_name,
                )
            )
            workbooks, _ = self._tableau_server.workbooks.get(req_options)

            if not workbooks:
                print("[Tableau]   По Name не найден, пробую ContentUrl...")
                req_options2 = TSC.RequestOptions()
                req_options2.filter.add(
                    TSC.Filter(
                        TSC.RequestOptions.Field.ContentUrl,
                        TSC.RequestOptions.Operator.Equals,
                        search_name,
                    )
                )
                workbooks, _ = self._tableau_server.workbooks.get(req_options2)

            if not workbooks:
                all_wbs, _ = self._tableau_server.workbooks.get()
                names = [w.name for w in all_wbs]
                print(f"[Tableau]   Все воркбуки ({len(names)}): {names}")
                raise ValueError(f"Воркбук '{search_name}' не найден на Tableau Server")

            wb = workbooks[0]
            print(f"[Tableau]   Найден воркбук: {repr(wb.name)} (id={wb.id})")
            self._tableau_server.workbooks.populate_views(wb)

            print(f"[Tableau]   Листы ({len(wb.views)}):")
            for v in wb.views:
                print(f"[Tableau]     name={repr(v.name)}  content_url={repr(v.content_url)}")

            view_id = None
            if target_sheet_name:
                view = next(
                    (
                        v
                        for v in wb.views
                        if target_sheet_name in (v.content_url or "") or target_sheet_name == v.name
                    ),
                    None,
                )
                if view:
                    view_id = view.id
                    print(f"[Tableau]   Используем лист: {repr(view.name)}")
                else:
                    print(f"[Tableau]   ??  Лист {repr(target_sheet_name)} не найден — берем первый")

            if not view_id and wb.views:
                view_id = wb.views[0].id
                print(f"[Tableau]   Первый лист: {repr(wb.views[0].name)}")

            endpoint = (
                f"{self._tableau_server_url}/api/{self._tableau_server.version}"
                f"/sites/{self._tableau_server.site_id}/views/{view_id}/data"
            )
            headers = {"X-Tableau-Auth": self._tableau_server.auth_token}

            print(f"[Tableau]   GET {endpoint}")
            print(f"[Tableau]   Params: {parameters}")

            resp = requests.get(
                endpoint,
                headers=headers,
                params=parameters,
                verify=False,
                timeout=60,
            )

            if resp.status_code != 200:
                raise Exception(f"Ошибка выгрузки ({resp.status_code}): {resp.text[:300]}")

            df = pd.read_csv(io.BytesIO(resp.content))
            print(f"[Tableau]   ? Получено {len(df)} строк, {len(df.columns)} колонок")
            return df
