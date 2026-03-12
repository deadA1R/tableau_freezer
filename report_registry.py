BASE_DETAILED_REPORT = """SELECT * FROM (
                  SELECT "s_current_account_info"."ACCOUNT_KIND" AS "account_kind",
                        "s_current_account_info"."ACCOUNT_NAME" AS "account_name",
                        "s_current_account_info"."ACC_TYPE" AS "acc_type",
                        "custom_sql_query"."ACT_DATE" AS "act_date__custom_sql_query_",
                        "s_security_operation_info"."ACT_DATE" AS "act_date",
                        "dm_limit_contract"."AMOUNT_CLOSE" AS "amount_close",
                        "dm_limit_value"."APPROVED_GROUP_LIMIT" AS "approved_group_limit",
                        "dm_limit_value"."APPROVED_LIMIT_VALUE" AS "approved_limit_value",
                        "dm_limit_contract"."AVG_MRKT_RATE" AS "avg_mrkt_rate",
                        "dm_limit_contract"."BALANCE_AMOUNT_FCY" AS "balance_amount_fcy",
                        "dm_limit_contract"."BALANCE_AMOUNT_LCY" AS "balance_amount_lcy",
                        "dm_limit_value"."BANK_ACTIVE" AS "bank_active",
                        "dm_limit_value"."BANK_BIK" AS "bank_bik",
                        "dm_limit_value"."BANK_CAPITAL" AS "bank_capital",
                        "dm_limit_value"."BANK_CAPITAL_VALUE" AS "bank_capital_value",
                        "dm_limit_value"."BANK_ID" AS "bank_id__dm_limit_value_",
                        "dm_limit_contract"."BANK_ID" AS "bank_id",
                        "dm_limit_value"."BANK_NAME" AS "bank_name__dm_limit_value_",
                        "dm_limit_contract"."BANK_NAME" AS "bank_name",
                        "dm_limit_value"."BANK_RATING" AS "bank_rating",
                        "dm_limit_contract"."BANK_SIGN" AS "bank_sign",
                        "s_current_account_info"."BASIS_CHARGE_NAME" AS "basis_charge_name",
                        "dm_limit_contract"."CLOSING_VALUE" AS "closing_value",
                        "dm_limit_contract"."CONTRACT_NAME" AS "contract_name",
                        "dm_limit_contract"."CONTRACT_TYPE" AS "contract_type",
                        "dm_limit_contract"."COUNTERPARTY_RATING_RANGE" AS "counterparty_rating_range",
                        "dm_limit_contract"."COUPON_IR_KIND" AS "coupon_ir_kind",
                        "dm_limit_contract"."CPN_RATE" AS "cpn_rate",
                        "di_exchange_rates"."CURRENCY_CODE" AS "currency_code__di_exchange_rates_",
                        "s_current_account_info"."CURRENCY_CODE" AS "currency_code__s_current_account_info_",
                        "dm_limit_contract"."CURRENCY_CODE" AS "currency_code",
                        "s_security_operation_info"."CURRENCY_CODE_STR" AS "currency_code_str",
                        "s_current_account_info"."DATE_BEGIN" AS "date_begin",
                        "s_current_account_info"."DATE_CLOSE" AS "date_close",
                        "s_current_account_info"."DATE_END" AS "date_end__s_current_account_info_",
                        "dm_limit_contract"."DATE_END" AS "date_end",
                        "s_current_account_info"."DATE_OPEN" AS "date_open",
                        "dm_limit_contract"."DATE_START" AS "date_start",
                        "dm_limit_value"."DISTRIBUTION_RATE" AS "distribution_rate",
                        "dm_limit_value"."DM_DATE" AS "dm_date__dm_limit_value_",
                        "dm_limit_contract"."DM_DATE" AS "dm_date",
                        "dm_limit_contract"."EMISSION_DATE" AS "emission_date",
                        "di_exchange_rates"."EX_DATE" AS "ex_date",
                        "dm_limit_contract"."FEE_SUM_FCY" AS "fee_sum_fcy",
                        "dm_limit_contract"."FEE_SUM_LCY" AS "fee_sum_lcy",
                        "s_current_account_info"."FIN_SOURCE" AS "fin_source",
                        "dm_limit_contract"."FIN_SOURCE_NAME" AS "fin_source_name",
                        "s_current_account_info"."GUARANTEE_NUMBER" AS "guarantee_number",
                        "dm_limit_contract"."GUAR_PROJ_NAME" AS "guar_proj_name",
                        "s_current_account_info"."HASH" AS "hash__s_current_account_info_",
                        "s_security_operation_info"."HASH" AS "hash",
                        "s_current_account_info"."H_CURRENT_ACCOUNT_ID" AS "h_current_account_id",
                        "h_lot_of_security"."H_LOT_OF_SECURITY_BK" AS "h_lot_of_security_bk",
                        "l_security_operation"."H_LOT_OF_SECURITY_ID" AS "h_lot_of_security_id__l_security_operation_",
                        "h_lot_of_security"."H_LOT_OF_SECURITY_ID" AS "h_lot_of_security_id",
                        "h_lot_of_security"."H_LOT_OF_SECURITY_LOAD_DATE" AS "h_lot_of_security_load_date",
                        "h_lot_of_security"."H_LOT_OF_SECURITY_SOURCE_NAME" AS "h_lot_of_security_source_name",
                        "l_security_operation"."H_SECURITY_ID" AS "h_security_id",
                        "s_security_operation_info"."H_SECURITY_OPERATION_ID" AS "h_security_operation_id__s_security_operation_info_",
                        "l_security_operation"."H_SECURITY_OPERATION_ID" AS "h_security_operation_id",
                        "s_current_account_info"."IBAN" AS "iban",
                        "dm_limit_contract"."INC_TOTAL_AMOUNT_INVESTMENT_INCOME" AS "inc_total_amount_investment_income",
                        "dm_limit_contract"."INTEREST_BASE" AS "interest_base",
                        "dm_limit_contract"."INTEREST_PERIOD" AS "interest_period",
                        "dm_limit_contract"."INTEREST_RATE" AS "interest_rate",
                        "s_current_account_info"."IR_VALUE" AS "ir_value",
                        "s_current_account_info"."IS_ACTUAL" AS "is_actual",
                        "l_security_operation"."IS_DELETED" AS "is_deleted",
                        "dm_limit_value"."IS_FOREIGN_AFFIL" AS "is_foreign_affil",
                        "custom_sql_query"."LIMIT_DEAL_ID" AS "limit_deal_id__custom_sql_query_",
                        "dm_limit_contract"."LIMIT_DEAL_ID" AS "limit_deal_id",
                        "dm_limit_contract"."LIMIT_TOOL_CODE" AS "limit_tool_code",
                        "dm_limit_contract"."LIMIT_TOOL_NAME" AS "limit_tool_name",
                        "di_exchange_rates"."LOAD_DATE" AS "load_date__di_exchange_rates_",
                        "dm_limit_value"."LOAD_DATE" AS "load_date__dm_limit_value_",
                        "s_current_account_info"."LOAD_DATE" AS "load_date__s_current_account_info_",
                        "s_security_operation_info"."LOAD_DATE" AS "load_date__s_security_operation_info_",
                        "dm_limit_contract"."LOAD_DATE" AS "load_date",
                        "s_security_operation_info"."LOT_ID" AS "lot_id",
                        "l_security_operation"."L_SECURITY_OPERATION_ID" AS "l_security_operation_id",
                        "l_security_operation"."L_SECURITY_OPERATION_LOAD_DATE" AS "l_security_operation_load_date",
                        "dm_limit_value"."MAX_LIMIT_VALUE" AS "max_limit_value",
                        "dm_limit_contract"."MIN_RATING_SCALE" AS "min_rating_scale",
                        "dm_limit_contract"."NOMINAL_AMOUNT" AS "nominal_amount",
                        "dm_limit_contract"."NOT_INCLUDED_TO_INCOME" AS "not_included_to_income__dm_limit_contract_",
                        "s_current_account_info"."NOT_INCLUDED_TO_INCOME" AS "not_included_to_income",
                        "s_current_account_info"."NOT_INCLUDED_TO_MAX_LIMIT" AS "not_included_to_max_limit",
                        "dm_limit_contract"."NOT_IN_VSDS" AS "not_in_vsds__dm_limit_contract_",
                        "s_current_account_info"."NOT_IN_VSDS" AS "not_in_vsds",
                        "s_current_account_info"."NOT_REDUCE_MINIMAL_BALANCE_OF_ACCOUNT_NUMBER" AS "not_reduce_minimal_balance_of_account_number__s_current_account",
                        "dm_limit_contract"."NOT_REDUCE_MINIMAL_BALANCE_OF_ACCOUNT_NUMBER" AS "not_reduce_minimal_balance_of_account_number",
                        "dm_limit_contract"."NUMBER" AS "number",
                        "s_security_operation_info"."OPERATION_AMOUNT_FCY" AS "operation_amount_fcy",
                        "dm_limit_contract"."OPERATION_AMOUNT_LCY" AS "operation_amount_lcy__dm_limit_contract_",
                        "s_security_operation_info"."OPERATION_AMOUNT_LCY" AS "operation_amount_lcy",
                        "s_security_operation_info"."OPERATION_TYPE" AS "operation_type",
                        "dm_limit_value"."ORGANIZATION_CAPITAL" AS "organization_capital",
                        "dm_limit_value"."ORGANIZATION_CAPITAL_VALUE" AS "organization_capital_value",
                        "dm_limit_value"."ORGANIZATION_ID" AS "organization_id__dm_limit_value_",
                        "dm_limit_contract"."ORGANIZATION_ID" AS "organization_id",
                        "dm_limit_value"."ORGANIZATION_NAME" AS "organization_name",
                        "dm_limit_contract"."ORGANIZATION_NAME_LEGAL" AS "organization_name_legal",
                        "dm_limit_contract"."ORGANIZATION_NAME_SHORT" AS "organization_name_short",
                        "dm_limit_contract"."ORG_FLAG" AS "org_flag",
                        "s_current_account_info"."ORIGINAL_AMOUNT_OF_ACCOUNT_NUMBER" AS "original_amount_of_account_number__s_current_account_info_",
                        "dm_limit_contract"."ORIGINAL_AMOUNT_OF_ACCOUNT_NUMBER" AS "original_amount_of_account_number",
                        "dm_limit_value"."PARENT_ORGANIZATION_NAME_SHORT" AS "parent_organization_name_short__dm_limit_value_",
                        "dm_limit_contract"."PARENT_ORGANIZATION_NAME_SHORT" AS "parent_organization_name_short",
                        "s_current_account_info"."PERIODICITY_NAME" AS "periodicity_name",
                        "dm_limit_contract"."PERIODICITY_PAYMENT_REMUNERATION" AS "periodicity_payment_remuneration",
                        "s_security_operation_info"."PRICE" AS "price",
                        "dm_limit_contract"."QUANTITY" AS "quantity__dm_limit_contract_",
                        "s_security_operation_info"."QUANTITY" AS "quantity",
                        "dm_limit_contract"."QUANTITY_REMAINING_BALANCE" AS "quantity_remaining_balance",
                        "dm_limit_value"."RATING_SCALE" AS "rating_scale",
                        "dm_limit_value"."RELATED_BANK_ID" AS "related_bank_id",
                        "dm_limit_value"."RELATED_BANK_NAME" AS "related_bank_name",
                        "dm_limit_contract"."REPAYMENT_AMOUNT" AS "repayment_amount",
                        "dm_limit_contract"."REPORT_DATE" AS "report_date",
                        "dm_limit_contract"."RESERVE_SUM" AS "reserve_sum",
                        "dm_limit_contract"."RESIDENCE_SIGN" AS "residence_sign",
                        "dm_limit_contract"."SECURITY_RATING" AS "security_rating",
                        "dm_limit_contract"."SECURITY_RATING_SCALE" AS "security_rating_scale",
                        "dm_limit_contract"."SECURITY_YIELD" AS "security_yield",
                        "dm_limit_contract"."START_BALANCE_AMOUNT" AS "start_balance_amount",
                        "dm_limit_contract"."TOTAL_NOMINAL_VALUE" AS "total_nominal_value",
                        "dm_limit_contract"."TOTAL_PROVISION_ON_COUPON" AS "total_provision_on_coupon",
                        "s_security_operation_info"."TRANSACTION_ID" AS "transaction_id",
                        "di_exchange_rates"."VALUE" AS "value",
                        "custom_sql_query"."dohod" AS "dohod",
                        "custom_sql_query"."p_ACT_DATE" AS "p_act_date",
                        "custom_sql_query"."p_type" AS "p_type",
                        "custom_sql_query"."type" AS "type"
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
            WHERE "dm_limit_contract"."LIMIT_TOOL_CODE" = {ToolCode}
            and NOT("dm_limit_contract"."ORGANIZATION_NAME_LEGAL" IS NULL OR "dm_limit_contract"."ORGANIZATION_NAME_LEGAL" = 'ЧАСТНАЯ КОМПАНИЯ BGLOBAL VENTURES LTD.')
            AND "dm_limit_contract"."DM_DATE" >= '{DateStart}'
            AND "dm_limit_contract"."DM_DATE" <= '{DateEnd}'"""

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
 