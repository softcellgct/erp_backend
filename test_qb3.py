import asyncio
from sqlalchemy import select
from common.models.billing.fee_structure import FeeHead
from components.utils.query_builder import build_safe_query
from fastapi_querybuilder.params import QueryParams

filters_json = '{"$and":[{"field":"academic_year_id","operator":"$eq","value":"68a805d8-438c-44e3-bd58-9094bf26a0f9"},{"field":"institution_id","operator":"$eq","value":"82917b80-732e-4299-9af5-d34b84b19123"}]}'
params = QueryParams(filters=filters_json)
try:
    query = build_safe_query(FeeHead, params)
    print("SUCCESS")
    print(str(query.compile(compile_kwargs={"literal_binds": True})))
except Exception as e:
    print("EXCEPTION:", type(e), e)
