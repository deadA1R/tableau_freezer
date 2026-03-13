import os
import io
import urllib3
import pandas as pd
import tableauserverclient as TSC
import requests
import pantab
from pathlib import Path
from urllib.parse import unquote
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

MOCK_MODE = True 

class TableauFreezer:
    def __init__(self):
        self.server_url = os.getenv('TABLEAU_SERVER_URL')
        
        if not MOCK_MODE:
            self.token_name = os.getenv('TABLEAU_TOKEN_NAME')
            self.token_value = os.getenv('TABLEAU_TOKEN_VALUE')
            self.site_id = os.getenv('TABLEAU_SITENAME', '')
            
            self.auth = TSC.PersonalAccessTokenAuth(
                token_name=self.token_name, 
                personal_access_token=self.token_value, 
                site_id=self.site_id
            )
            self.server = TSC.Server(self.server_url, use_server_version=True)
            self.server.add_http_options({'verify': False})
        else:
            print("🏗 [MOCK MODE] Инициализация для демо-показа...")

    def get_view_data(self, workbook_name_or_path: str, parameters: dict = None):
        """Универсальный метод: ищет данные по имени или пути."""
        
        if MOCK_MODE:
            print(f"🔍 [MOCK] Поиск воркбука: {workbook_name_or_path}")
            mock_file = Path("mock_data.csv")
            if mock_file.exists():
                print(f"📖 [MOCK] Загрузка из {mock_file}")
                return pd.read_csv(mock_file)
            else:
                return pd.DataFrame({'Target': ['Mock'], 'Value': [0]})

        with self.server.auth.sign_in(self.auth):
            print(f"🔍 Начинаю поиск для: {workbook_name_or_path}")

            target_sheet_name = None
            search_name = workbook_name_or_path

            if "/" in workbook_name_or_path:
                parts = unquote(workbook_name_or_path).replace("views/", "").split("/")
                search_name = parts[0]
                target_sheet_name = parts[-1].split("?")[0]

            req_options = TSC.RequestOptions()
            req_options.filter.add(TSC.Filter(TSC.RequestOptions.Field.Name,
                                             TSC.RequestOptions.Operator.Equals,
                                             search_name))
            workbooks, _ = self.server.workbooks.get(req_options)
            
            if not workbooks:
                req_options = TSC.RequestOptions()
                req_options.filter.add(TSC.Filter(TSC.RequestOptions.Field.ContentUrl,
                                                 TSC.RequestOptions.Operator.Equals,
                                                 search_name))
                workbooks, _ = self.server.workbooks.get(req_options)

            if not workbooks:
                raise ValueError(f"Воркбук '{search_name}' не найден.")

            target_workbook = workbooks[0]
            self.server.workbooks.populate_views(target_workbook)
            
            view_id = None
            if target_sheet_name:
                view_id = next((v.id for v in target_workbook.views if target_sheet_name in v.content_url or target_sheet_name == v.name), None)
            
            if not view_id and target_workbook.views:
                view_id = target_workbook.views[0].id

            endpoint = f"{self.server_url}/api/{self.server.version}/sites/{self.server.site_id}/views/{view_id}/data"
            headers = {'X-Tableau-Auth': self.server.auth_token}
            
            response = requests.get(endpoint, headers=headers, params=parameters, verify=False)
            if response.status_code != 200:
                raise Exception(f"Ошибка выгрузки ({response.status_code}): {response.text}")
            
            return pd.read_csv(io.BytesIO(response.content))

    def save_to_hyper(self, df: pd.DataFrame, filename: str = "freeze_extract.hyper"):
        if df.empty:
            print("⚠️ DataFrame пуст.")
            return None
        
        df.columns = [str(col).strip() for col in df.columns]
        
        for col in df.columns:
            if 'дата' in col.lower() or 'date' in col.lower():
                try:
                    df[col] = pd.to_datetime(df[col], dayfirst=True)
                    continue 
                except: pass

            if df[col].dtype == 'object':
                try:
                    cleaned = df[col].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.')
                    df[col] = pd.to_numeric(cleaned)
                    print(f"✅ Колонка {col} сконвертирована в число")
                except:
                    df[col] = df[col].astype(str)
                        
        hyper_temp = Path("hyper_temp")
        hyper_temp.mkdir(exist_ok=True)
        os.environ["HYPER_LOG_DIR"] = str(hyper_temp.absolute())

        path = Path(filename)
        if path.exists():
            try:
                path.unlink()
            except PermissionError:
                print(f"❌ Файл {filename} занят.")
                return None

        print(f"🚀 Запуск упаковки в Hyper (строк: {len(df)})...")
        try:
            pantab.frame_to_hyper(df, path, table="Extract")
            print(f"❄️ Данные успешно заморожены: {path.absolute()}")
            return path
        except Exception as e:
            print(f"❌ Ошибка Hyper API: {e}")
            raise
        
    def publish_hyper_source(self, file_path: Path, project_name: str, datasource_name: str):
        """Публикация (с MOCK-заглушкой)."""
        if MOCK_MODE:
            print(f"☁️ [MOCK] Имитация публикации {datasource_name} в {project_name}...")
            return "mock-id"

        with self.server.auth.sign_in(self.auth):
            all_projects, _ = self.server.projects.get()
            project = next((p for p in all_projects if p.name == project_name), None)
            
            if not project:
                raise ValueError(f"Проект '{project_name}' не найден.")

            new_datasource = TSC.DatasourceItem(project.id, name=datasource_name)
            published_ds = self.server.datasources.publish(
                new_datasource, str(file_path), TSC.Server.PublishMode.Overwrite
            )
            print(f"✅ Успешно опубликовано! ID: {published_ds.id}")
            return published_ds.id


if __name__ == "__main__":
    freezer = TableauFreezer()
    
    target_path = "_17682043209580/1_1_1/Слайд 1. Отчет по операциям репо (1.1)"
    
    my_params = {
        "Дата начала периода": "01.01.2025",
        "Дата окончания периода": "31.01.2025"
    }

    archive_name = f"Архив_РЕПО_{my_params['Дата начала периода']}_{my_params['Дата окончания периода']}"
    target_project = "Замороженные Источники данных"
    
    try:
        data_df = freezer.get_view_data(target_path, my_params)
        local_hyper = freezer.save_to_hyper(data_df, "repo_snapshot_copy.hyper")
        if local_hyper:
            freezer.publish_hyper_source(local_hyper, target_project, archive_name)
        
    except Exception as e:
        print(f"❌ Произошла ошибка: {e}")