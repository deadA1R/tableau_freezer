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
    "Слайд 1. Отчет по операциям репо (1.1)":"FROZEN_DATA_DETAILED_REPORT",
    "Слайд 2.1 Отчет о депозитах в разрезе источников финансировани (1.2)": "FROZEN_DATA_DETAILED_REPORT",
    "Слайд 3.1 Отчет о текущих счетах в разрезе источников финансирования (1.3)": "FROZEN_DATA_DETAILED_REPORT",
    "Слайд 5. Отчет по портфелю ЦБ (1.4)": "FROZEN_DATA_DETAILED_REPORT",
    "Слайд 6. Отчет по дебиторской задолженности в разрезе источников финансирования (1.5)": "FROZEN_DATA_DETAILED_REPORT",
    "Слайд 7. Отчет о кредитах, выданных БВУ в разрезе источников финансирования (1.6)": "FROZEN_DATA_DETAILED_REPORT",
    "Слайд 8. Отчет по гарантиям, выданным БВУ в разрезе источников финансирования (1.7)": "FROZEN_DATA_DETAILED_REPORT",
    "Слайд 9. Отчет об иных требованиях к БВУ в разрезе источников финансирования (1.8)": "FROZEN_DATA_DETAILED_REPORT",
    "Слайд 5.1. Отчет по доходности депозитов в тенге": "FROZEN_PROFITABILITY_REPORT_MAIN",
    "Слайд 5.2. Отчет по доходности депозитов в валюте": "FROZEN_PROFITABILITY_REPORT_MAIN_CURRENCY",
    "Слайд 5.3. Отчет по доходности текущих счетов в тенге": "FROZEN_PROFITABILITY_REPORT_MAIN",
    "Слайд 5.4. Отчет по доходности текущих счетов в валюте": "FROZEN_PROFITABILITY_REPORT_MAIN_CURRENCY",
    "Слайд 5.5. Отчет по доходности ЦБ в тенге": "FROZEN_PROFITABILITY_REPORT_SECURITIES",
    "Слайд 5.6. Отчет по доходности ЦБ в валюте": "FROZEN_PROFITABILITY_REPORT_SECURITIES",
    "Слайд 5.7. Отчет по доходности операций репо": "FROZEN_PROFITABILITY_REPORT_MAIN",
    "Слайд 5.8. Сводная форма доходности Финансовых инструментов": "FROZEN_FULL_REPORT_PROFITABILITY",
}