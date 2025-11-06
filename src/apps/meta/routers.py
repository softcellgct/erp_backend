from common.models.meta.models import Religion, Community, Caste
from common.schemas.meta.religion_schemas import (
    ReligionCreate,
    ReligionUpdate,
    ReligionResponse,
)
from common.schemas.meta.community_schemas import (
    CommunityCreate,
    CommunityUpdate,
    CommunityResponse,
)
from common.schemas.meta.caste_schemas import CasteCreate, CasteUpdate, CasteResponse
from components.generator.routes import create_crud_routes
from fastapi import APIRouter


religion_router = APIRouter()

religion_crud = create_crud_routes(
    Religion,
    CreateSchema=ReligionCreate,
    UpdateSchema=ReligionUpdate,
    AllResponseSchema=ReligionResponse,
    IdResponseSchema=ReligionResponse,
)

religion_router.include_router(
    religion_crud, prefix="/religions", tags=["Meta - Religions"]
)


# =====================================================
# Community CRUD Routes
# =====================================================
community_router = APIRouter()

community_crud = create_crud_routes(
    Community,
    CreateSchema=CommunityCreate,
    UpdateSchema=CommunityUpdate,
    AllResponseSchema=CommunityResponse,
    IdResponseSchema=CommunityResponse,
)

community_router.include_router(
    community_crud, prefix="/communities", tags=["Meta - Communities"]
)


# =====================================================
# Caste CRUD Routes
# =====================================================
caste_router = APIRouter()

caste_crud = create_crud_routes(
    Caste,
    CreateSchema=CasteCreate,
    UpdateSchema=CasteUpdate,
    AllResponseSchema=CasteResponse,
    IdResponseSchema=CasteResponse,
)

caste_router.include_router(caste_crud, prefix="/castes", tags=["Meta - Castes"])
