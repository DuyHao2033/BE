from pydantic import BaseModel
from typing import List

class FontRead(BaseModel):
    name: str
    filename: str

class FontListResponse(BaseModel):
    items: List[FontRead]
    total: int
