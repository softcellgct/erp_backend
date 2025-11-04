from uuid import UUID
from common.models.admission.consultancy import ProofType
from pydantic import BaseModel
from typing import Optional


class ConsultancyBase(BaseModel):
    name: str
    address: str
    contact_person: str
    contact_person_email: str
    contact_person_phone: str
    proof_type: ProofType
    contact_person_proof_number: str
    contact_person_proof_url: str
    is_active: bool = True

class ConsultancyCreate(ConsultancyBase):
    pass

class ConsultancyUpdate(BaseModel):
    id: UUID
    name: Optional[str] = None
    address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_person_email: Optional[str] = None
    contact_person_phone: Optional[str] = None
    proof_type: Optional[ProofType] = None
    contact_person_proof_number: Optional[str] = None
    contact_person_proof_url: Optional[str] = None
    is_active: Optional[bool] = None

class ConsultancyResponse(ConsultancyBase):
    id: UUID

    class Config:
        from_attributes = True


