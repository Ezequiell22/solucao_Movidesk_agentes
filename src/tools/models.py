from typing import List, Optional, Any
from pydantic import BaseModel, Field

class Person(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    personType: Optional[int] = None
    profileType: Optional[int] = None

class Comment(BaseModel):
    id: Optional[int] = None
    type: int
    body: str
    createdDate: Optional[str] = None
    createdBy: Optional[Person] = None

class CustomFieldValue(BaseModel):
    customFieldId: int
    customFieldRuleId: int
    value: Optional[str] = None
    items: Optional[List[Any]] = []

class Ticket(BaseModel):
    id: Optional[str] = None
    protocol: Optional[str] = None
    type: Any
    subject: str
    category: Optional[str] = None
    urgency: Optional[str] = None
    status: str
    baseStatus: Optional[str] = None
    justification: Optional[str] = None
    origin: Optional[Any] = None
    createdDate: Optional[str] = None
    owner: Optional[Any] = None
    ownerTeam: Optional[str] = None
    createdBy: Optional[Any] = None
    tags: Optional[Any] = []
    comments: Optional[Any] = []
    customFieldValues: Optional[Any] = []
    # Simplified others for MVP as requested to not invent
    serviceFirstLevel: Optional[str] = None
    serviceSecondLevel: Optional[str] = None
    serviceThirdLevel: Optional[str] = None
