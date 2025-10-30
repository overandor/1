from pydantic import BaseModel
from typing import List, Dict

class KPI(BaseModel):
    id: str
    name: str
    description: str
    formula: str

class Prompt(BaseModel):
    id: str
    text: str

class Appraisal(BaseModel):
    prompt_id: str
    scores: Dict[str, float]
