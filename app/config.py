ADMINS = [
    'tabladmin', 
    'drp_exp'
]

REPORT_5_8_NAME      = "Слайд 5.8. Сводная форма доходности Финансовых инструментов"
REPORT_5_8_WORKBOOK  = "Отчеты по доходности"
REPORT_5_8_WORKSHEET = "Слайд 5.8. Сводная форма доходности Финансовых инструментов"

REPORTS_WITH_REPORT_DATE = {
    "Слайд 5.5. Отчет по доходности ЦБ в тенге",
    "Слайд 5.6. Отчет по доходности ЦБ в валюте",
}

FROZEN_TABLE_FALLBACK = "FROZEN_DATA_DETAILED_REPORT"

REPORT_FROZEN_TABLE_MAP: dict[str, str] = {
    # Пример:
    # "Отчёт 5.1": "FROZEN_DATA_REPORT_5_1",
    # "Отчёт 5.8": "FROZEN_DATA_REPORT_5_8",
    # REPORT_5_8_NAME: "FROZEN_SUMMARY_REPORT_PROFITABILITY",  ← уже пишется отдельно
    # Добавляй по аналогии для каждого отчёта
}

ADMINS = [
    'tabladmin', 
    'drp_exp'
]