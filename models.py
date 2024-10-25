from pydantic import BaseModel, Field, EmailStr, validator
from typing import List, Optional
from datetime import datetime, timezone

class Participante(BaseModel):
    id: str = Field(..., example="p1")
    name: str = Field(..., example="Juan Pérez")
    email: EmailStr = Field(..., example="juan.perez@example.com")
    registration_date: str = Field(default_factory=datetime.utcnow)

class Evento(BaseModel):
    id: str = Field(..., example="e1")
    name: str = Field(..., example="Conferencia Tech 2024")
    description: Optional[str] = Field(None, example="Una conferencia sobre las últimas tendencias en tecnología.")
    date: str = Field(..., example="2024-09-15T09:00:00Z")
    location: str = Field(..., example="Centro de Convenciones Ciudad")
    capacity: int = Field(..., ge=1, example=300)
    participants: List[Participante] = Field(default_factory=list)

        