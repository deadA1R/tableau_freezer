import os
from dotenv import load_dotenv
import tableauserverclient as TSC


import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

def test_connection():
    server_url = os.getenv('TABLEAU_SERVER_URL')
    token_name = os.getenv('TABLEAU_TOKEN_NAME')
    token_value = os.getenv('TABLEAU_TOKEN_VALUE')
    site_id = os.getenv('TABLEAU_SITENAME', '')

    tableau_auth = TSC.PersonalAccessTokenAuth(
        token_name=token_name, 
        personal_access_token=token_value, 
        site_id=site_id
    )
    
    server = TSC.Server(server_url, use_server_version=True)
    server.add_http_options({'verify': False})
    
    try:
        print(f"Попытка входа на {server_url} (Site: '{site_id}')...")
        with server.auth.sign_in(tableau_auth):
            print("✅ Коннект с Tableau есть! Мы внутри.")

            all_projects, pagination = server.projects.get()
            print(f"Успешно получено проектов: {len(all_projects)}")
            for project in all_projects[:5]:
                print(f" - Проект: {project.name}")
                
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

if __name__ == "__main__":
    test_connection()