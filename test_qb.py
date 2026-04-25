import asyncio
from sqlalchemy import select
from src.common.models.billing.financial_year import FinancialYear
from src.components.utils.query_builder import build_safe_query
from fastapi_querybuilder.params import QueryParams

params = QueryParams(filters='{"$and":[{"field":"active","operator":"$eq","value":true}]}')
try:
    query = build_safe_query(FinancialYear, params)
    print("SUCCESS")
except Exception as e:
    print("EXCEPTION:", type(e), e)
