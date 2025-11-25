from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# --- Agent (Modify) Models ---
class ChatRequest(BaseModel):
    prompt: str
    context: str

class AgentResponse(BaseModel):
    intention: str
    reply: str
    modified_data: Optional[Dict[str, Any]] = None

# --- Review Models ---
class ReviewRequest(BaseModel):
    resume_content: str

class ReviewResponse(BaseModel):
    score: int
    summary: str
    pros: List[str]
    cons: List[str]
    suggestions: List[str]