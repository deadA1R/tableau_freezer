ADMINS = [
    'tabladmin', 
    'drp_exp'
]

WORKFLOW_CONTEXT_COLUMNS: dict[str, str] = {
    "SESSION_ID": "TEXT",
    "EVENT_ID": "TEXT",
    "EVENT_TYPE": "TEXT",
    "PUBLIC_IP_CANDIDATE": "TEXT",
}

WORKFLOW_EXTENDED_COLUMNS: dict[str, str] = {
    "FREEZE_TASK_ID": "TEXT",
    "SESSION_ID": "TEXT",
    "EVENT_ID": "TEXT",
    "EVENT_TYPE": "TEXT",
    "TIMESTAMP_UTC": "TEXT",
    "USER_AGENT": "TEXT",
    "ACCEPT_LANGUAGE": "TEXT",
    "SEC_CH_UA": "TEXT",
    "SEC_CH_UA_PLATFORM": "TEXT",
    "DEVICE_TYPE": "TEXT",
    "TABLEAU_USER": "TEXT",
    "DASHBOARD": "TEXT",
    "PUBLIC_IP_CANDIDATE": "TEXT",
}

REPORT_5_8_NAME      = "Слайд 5.8. Сводная форма доходности Финансовых инструментов"
REPORT_5_8_WORKBOOK  = "Слайд 5.8. Сводная форма доходности Финансовых инструментов"
REPORT_5_8_WORKSHEET = "5.8. ИТОГО"

REPORTS_WITH_REPORT_DATE = {
    "Слайд 5.5. Отчет по доходности ЦБ в тенге",
    "Слайд 5.6. Отчет по доходности ЦБ в валюте",
}