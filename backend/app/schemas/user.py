import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    role: str
    client_id: uuid.UUID | None
    must_change_password: bool
    is_active: bool
    created_at: datetime
