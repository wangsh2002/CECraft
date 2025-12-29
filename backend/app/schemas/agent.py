from pydantic import BaseModel
from typing import Optional, Dict, Any, List

# --- Agent (Modify) Models ---
class ChatRequest(BaseModel):
    prompt: str
    context: str
    history: List[Dict[str, str]] = []  # 新增：历史对话记录
    block_size: Optional[Dict[str, float]] = None # 新增：文本块大小限制 {width, height}

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