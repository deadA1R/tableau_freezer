# -*- coding: cp1251 -*-
USER_TO_ORGANIZATION = {
    # -- QIC --
    "g.kapan.qic":     "QIC",
    "t.beguliyev.qic": "QIC",
    
    # -- AKK --
    "ivanov.akk":  "АКК",
    "petrov.akk":  "АКК",
    
    # -- BRK --
    "vasya.brk":   "БРК",
    "masha.brk":   "БРК",
    
    # -- Холдинг (админы) --
    "tabladmin":             "Холдинг",
    "a.assetov":             "Холдинг",
    "drp_exp":               "Холдинг",
    "Iskakov_Aspandiyar_exp":"HOLDING",
}

DEFAULT_ORGANIZATION = "UNKNOWN"


def get_organization_for_user(username: str) -> str:
    return USER_TO_ORGANIZATION.get(username, DEFAULT_ORGANIZATION)