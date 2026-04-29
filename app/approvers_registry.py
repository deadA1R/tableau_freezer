# -*- coding: cp1251 -*-
APPROVERS_BY_USER = {
    # --QIC --
    "g.kapan.qic": [
        {"value": "t.beguliyev.qic", "label": "Бегулиев Т. (Руководитель ДО)"},
    ],
    
    # -- Руководители QIC --
    "t.beguliyev.qic": [
        {"value": "a.assetov", "label": "Асетов Азамат (Холдинг)"},
        {"value": "tabladmin", "label": "Tableau Admin (Холдинг)"},
    ],
    
}


DEFAULT_APPROVERS = [
    {"value": "tabladmin", "label": "Tableau Admin"},
]


def get_approvers_for_user(username: str):
    return APPROVERS_BY_USER.get(username, DEFAULT_APPROVERS)