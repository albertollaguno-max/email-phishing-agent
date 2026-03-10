from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from database import SenderType

# --- Allowed Sender Schemas ---
class AllowedSenderBase(BaseModel):
    type: SenderType
    value: str
    is_active: bool = True
    description: Optional[str] = None

class AllowedSenderCreate(AllowedSenderBase):
    pass

class AllowedSenderUpdate(BaseModel):
    type: Optional[SenderType] = None
    value: Optional[str] = None
    is_active: Optional[bool] = None
    description: Optional[str] = None

class AllowedSenderResponse(AllowedSenderBase):
    id: int

    class Config:
        from_attributes = True


# --- Email Log Schemas ---
class EmailAnalysisLogResponse(BaseModel):
    id: int
    message_id: str
    from_address: Optional[str]
    forwarded_by: str
    subject: Optional[str]
    date_received: datetime
    is_fraudulent: Optional[bool]
    ai_explanation: Optional[str]
    ai_provider_used: Optional[str]
    prompt_tokens: int
    completion_tokens: int
    response_sent_at: Optional[datetime]

    class Config:
        from_attributes = True

# --- System Logs ---
class SystemLogResponse(BaseModel):
    id: int
    timestamp: datetime
    level: str
    message: str

    class Config:
        from_attributes = True
