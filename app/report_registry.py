BASE_DETAILED_REPORT = """SELECT * FROM (
                  SELECT   
                        '{SnapshotID}'::VARCHAR(100) as "SNAPSHOT_ID",
                        '{InitUser}'::VARCHAR(100) as "INIT",
                        '{ApproverUser}'::VARCHAR(100) as "APPROVER",
                        '{DateStart}'::DATE AS "FREEZING_PERIOD_START",
                        '{DateEnd}'::DATE AS "FREEZING_PERIOD_END",
                        CURRENT_DATE as "DATE_FREEZE",
                        GETDATE() AS "LOAD_DATE",
                        "dm_limit_contract"."AMOUNT_CLOSE",
                        "dm_limit_contract"."AVG_MRKT_RATE",
                        "dm_limit_contract"."BALANCE_AMOUNT_FCY",
                        "dm_limit_contract"."BALANCE_AMOUNT_LCY",
                        "dm_limit_contract"."BANK_ID",
                        "dm_limit_contract"."BANK_NAME",
                        "dm_limit_contract"."CLOSING_VALUE",
                        "dm_limit_contract"."CONTRACT_NAME",
                        "dm_limit_contract"."CONTRACT_TYPE",
                        "dm_limit_contract"."COUNTERPARTY_RATING_RANGE",
                        "dm_limit_contract"."COUPON_IR_KIND",
                        "dm_limit_contract"."CPN_RATE",
                        "dm_limit_contract"."CURRENCY_CODE",
                        "dm_limit_contract"."DATE_END",
                        "dm_limit_contract"."DATE_START",
                        "dm_limit_contract"."DM_DATE",
                        "dm_limit_contract"."FEE_SUM_FCY",
                        "dm_limit_contract"."FEE_SUM_LCY",
                        "dm_limit_contract"."FIN_SOURCE_NAME",
                        "dm_limit_contract"."GUAR_PROJ_NAME",
                        "dm_limit_contract"."INC_TOTAL_AMOUNT_INVESTMENT_INCOME",
                        "dm_limit_contract"."INTEREST_BASE",
                        "dm_limit_contract"."INTEREST_RATE",
                        "dm_limit_contract"."LIMIT_DEAL_ID",
                        "dm_limit_contract"."LIMIT_TOOL_CODE",
                        "dm_limit_contract"."LIMIT_TOOL_NAME",
                        "dm_limit_contract"."MIN_RATING_SCALE",
                        "dm_limit_contract"."NOMINAL_AMOUNT",
                        "dm_limit_contract"."NOT_IN_VSDS",
                        "dm_limit_contract"."NOT_REDUCE_MINIMAL_BALANCE_OF_ACCOUNT_NUMBER",
                        "dm_limit_contract"."NUMBER",
                        "dm_limit_contract"."OPERATION_AMOUNT_LCY" AS "OPERATION_AMOUNT_LCY (DM_LIMIT_CONTRACT)",
                        "dm_limit_contract"."ORGANIZATION_ID",
                        "dm_limit_contract"."ORGANIZATION_NAME_LEGAL",
                        "dm_limit_contract"."ORGANIZATION_NAME_SHORT",
                        "dm_limit_contract"."ORIGINAL_AMOUNT_OF_ACCOUNT_NUMBER",
                        "dm_limit_contract"."PARENT_ORGANIZATION_NAME_SHORT",
                        "dm_limit_contract"."PERIODICITY_PAYMENT_REMUNERATION",
                        "dm_limit_contract"."QUANTITY" AS "QUANTITY (DM_LIMIT_CONTRACT)",
                        "dm_limit_contract"."QUANTITY_REMAINING_BALANCE",
                        "dm_limit_contract"."REPORT_DATE",
                        "dm_limit_contract"."RESERVE_SUM",
                        "dm_limit_contract"."SECURITY_RATING",
                        "dm_limit_contract"."SECURITY_RATING_SCALE",
                        "dm_limit_contract"."SECURITY_YIELD",
                        "dm_limit_contract"."TOTAL_NOMINAL_VALUE",
                        "dm_limit_contract"."TOTAL_PROVISION_ON_COUPON",
                        "dm_limit_value"."BANK_RATING",
                        "di_exchange_rates"."CURRENCY_CODE" AS "CURRENCY_CODE (DI_EXCHANGE_RATES)",
                        "di_exchange_rates"."VALUE",
                        "s_current_account_info"."IBAN",
                        "s_current_account_info"."ACC_TYPE",
                        "h_lot_of_security"."H_LOT_OF_SECURITY_BK",
                        "s_security_operation_info"."OPERATION_AMOUNT_FCY",
                        "s_security_operation_info"."OPERATION_AMOUNT_LCY",
                        "s_security_operation_info"."OPERATION_TYPE",
                        "s_security_operation_info"."PRICE",
                        "s_security_operation_info"."QUANTITY",
                        "s_security_operation_info"."TRANSACTION_ID",
                        "s_security_operation_info"."ACT_DATE",
                        "s_security_operation_info"."CURRENCY_CODE_STR",
                        "custom_sql_query"."ACT_DATE" AS "ACT_DATE (Custom SQL Query)",
                        "custom_sql_query"."LIMIT_DEAL_ID" AS "LIMIT_DEAL_ID (Custom SQL Query)",
                        "custom_sql_query"."dohod",
                        "custom_sql_query"."p_ACT_DATE",
                        "custom_sql_query"."p_type",
                        "custom_sql_query"."type"
                        FROM "DM"."DM_LIMIT_CONTRACT" "dm_limit_contract"
                        LEFT JOIN "DWH"."DI_EXCHANGE_RATES" "di_exchange_rates" ON (("dm_limit_contract"."CURRENCY_CODE" = "di_exchange_rates"."CURRENCY_CODE") AND ("dm_limit_contract"."DM_DATE" = "di_exchange_rates"."EX_DATE"))
                        LEFT JOIN "DM"."DM_LIMIT_VALUE" "dm_limit_value" ON (("dm_limit_contract"."BANK_ID" = "dm_limit_value"."BANK_ID") AND ("dm_limit_contract"."DM_DATE" = "dm_limit_value"."DM_DATE"))
                        LEFT JOIN "DWH"."S_CURRENT_ACCOUNT_INFO" "s_current_account_info" ON ("dm_limit_contract"."LIMIT_DEAL_ID" = "s_current_account_info"."H_CURRENT_ACCOUNT_ID")
                        LEFT JOIN "DWH"."H_LOT_OF_SECURITY" "h_lot_of_security" ON ("dm_limit_contract"."LIMIT_DEAL_ID" = "h_lot_of_security"."H_LOT_OF_SECURITY_ID")
                        LEFT JOIN "DWH"."L_SECURITY_OPERATION" "l_security_operation" ON (("dm_limit_contract"."LIMIT_DEAL_ID" = "l_security_operation"."H_LOT_OF_SECURITY_ID") AND (FALSE = "l_security_operation"."IS_DELETED"))
                        LEFT JOIN "DWH"."S_SECURITY_OPERATION_INFO" "s_security_operation_info" ON ("l_security_operation"."H_SECURITY_OPERATION_ID" = "s_security_operation_info"."H_SECURITY_OPERATION_ID")
                        LEFT JOIN (
                        select 
                            s.ACT_DATE,
                            s.LIMIT_DEAL_ID, 
                            BALANCE_AMOUNT_LCY - OPERATION_AMOUNT_LCY dohod,
                            s.type,	
                            p.ACT_DATE as p_ACT_DATE,
                            p.type AS p_type
                        from (
                            select 
                                ssoi.ACT_DATE,
                                hlos.H_LOT_OF_SECURITY_ID LIMIT_DEAL_ID, 
                                CASE WHEN ssoi.CURRENCY_CODE_STR = 'KZT' THEN ssoi.OPERATION_AMOUNT_LCY ELSE ssoi.OPERATION_AMOUNT_FCY*ders.VALUE END BALANCE_AMOUNT_LCY,
                                'покупка' as type
                            from dwh.H_LOT_OF_SECURITY hlos   --DM_LIMIT_CONTRACT.LIMIT_DEAL_ID на дату отчета
                            left join dwh.L_SECURITY_OPERATION lso ON hlos.H_LOT_OF_SECURITY_ID = lso.H_LOT_OF_SECURITY_ID 
                            left join dwh.S_SECURITY_OPERATION_INFO ssoi ON lso.H_SECURITY_OPERATION_ID = ssoi.H_SECURITY_OPERATION_ID
                                left join dwh.DI_EXCHANGE_RATES_SUKO ders ON ders.CURRENCY_CODE = ssoi.CURRENCY_CODE_STR and ders.EX_DATE  = ssoi.ACT_DATE
                            where ssoi.OPERATION_TYPE in ('Покупка ЦБ')
                            UNION 
                            select 
                                dm_date as ACT_DATE,
                                dlc.LIMIT_DEAL_ID, 
                                dlc.BALANCE_AMOUNT_FCY,
                                'limit_contract' as type
                            from dm.DM_LIMIT_CONTRACT dlc 
                            where 
                                dlc.LIMIT_TOOL_CODE = 3 
                                and dlc.BALANCE_AMOUNT_FCY is not null
                                        and dlc.dm_date = DATE_TRUNC('year', dlc.dm_date)
                        ) s
                        join 
                            (
                                select 
                                    ssoi.ACT_DATE,
                                    hlos.H_LOT_OF_SECURITY_ID LIMIT_DEAL_ID,
                                    CASE WHEN ssoi.CURRENCY_CODE_STR = 'KZT' THEN ssoi.OPERATION_AMOUNT_LCY ELSE ssoi.OPERATION_AMOUNT_FCY*ders.VALUE END OPERATION_AMOUNT_LCY,
                                    'продажа' as type
                                from dwh.H_LOT_OF_SECURITY hlos   --DM_LIMIT_CONTRACT.LIMIT_DEAL_ID на дату отчета
                                left join dwh.L_SECURITY_OPERATION lso ON hlos.H_LOT_OF_SECURITY_ID = lso.H_LOT_OF_SECURITY_ID 
                                left join dwh.S_SECURITY_OPERATION_INFO ssoi ON lso.H_SECURITY_OPERATION_ID = ssoi.H_SECURITY_OPERATION_ID
                                        left join dwh.DI_EXCHANGE_RATES_SUKO ders ON ders.CURRENCY_CODE = ssoi.CURRENCY_CODE_STR and ders.EX_DATE  = ssoi.ACT_DATE
                                where 
                                    ssoi.OPERATION_TYPE in 
                                        ('Продажа ЦБ', 
                                        'Частичная продажа ЦБ', 
                                        'Погашение ЦБ в конце срока',
                                        'Досрочное погашение', 
                                        'Частичное погашение номинала')          
                                )
                        p ON s.LIMIT_DEAL_ID = p.LIMIT_DEAL_ID
                ) "custom_sql_query" ON ("dm_limit_contract"."LIMIT_DEAL_ID" = "custom_sql_query"."LIMIT_DEAL_ID")
            ) AS final_data
            WHERE final_data."LIMIT_TOOL_CODE" = {ToolCode}
            and NOT(final_data."ORGANIZATION_NAME_LEGAL" IS NULL OR final_data."ORGANIZATION_NAME_LEGAL" = 'ЧАСТНАЯ КОМПАНИЯ BGLOBAL VENTURES LTD.')
            AND final_data."DM_DATE" >= '{DateStart}'::DATE
            AND final_data."DM_DATE" <= '{DateEnd}'::DATE"""


REPORTS_SQL = {
    "Слайд 1. Отчет по операциям репо (1.1)": {
        "template": BASE_DETAILED_REPORT,
        "tool_code": 4
    },
    "Слайд 2.1 Отчет о депозитах в разрезе источников финансировани (1.2)": {
        "template": BASE_DETAILED_REPORT,
        "tool_code": 2  
    },
    "Слайд 3.1 Отчет о текущих счетах в разрезе источников финансирования (1.3)": {
        "template": BASE_DETAILED_REPORT,
        "tool_code": 1 
    },
    "Слайд 5. Отчет по портфелю ЦБ (1.4)": {
        "template": BASE_DETAILED_REPORT,
        "tool_code": 3  
    },
    "Слайд 6. Отчет по дебиторской задолженности в разрезе источников финансирования (1.5)": {
        "template": BASE_DETAILED_REPORT,
        "tool_code": 6
    },
    "Слайд 7. Отчет о кредитах, выданных БВУ в разрезе источников финансирования (1.6)": {
        "template": BASE_DETAILED_REPORT,
        "tool_code": 5  
    },
    "Слайд 8. Отчет по гарантиям, выданным БВУ в разрезе источников финансирования (1.7)": {
        "template": BASE_DETAILED_REPORT,
        "tool_code": 8  
    },
    "Слайд 9. Отчет об иных требованиях к БВУ в разрезе источников финансирования (1.8)": {
        "template": BASE_DETAILED_REPORT,
        "tool_code": 7  
    }
}
 