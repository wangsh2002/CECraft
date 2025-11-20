import os
from typing import Generator
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import dashscope
from http import HTTPStatus

# 请确保设置了环境变量 DASHSCOPE_API_KEY
# os.environ["DASHSCOPE_API_KEY"] = "你的通义千问API_KEY"

app = FastAPI()

# 配置 CORS，允许前端跨域调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境请替换为具体的前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    prompt: str
    context: str = ""


def call_qwen_stream(prompt: str, context: str) -> Generator[str, None, None]:
    """
    调用通义千问流式接口
    """
    # 构建 Prompt，将用户指令与上下文结合
    full_content = f"背景信息：用户正在编辑简历中的一段文本。\n文本内容：{context}\n\n用户指令：{prompt}\n\n请根据指令修改或润色上述文本。请直接输出修改后的结果，不要包含多余的解释。"
    
    messages = [
        {'role': 'system', 'content': '你是一个专业的简历优化助手。'},
        {'role': 'user', 'content': full_content}
    ]

    responses = dashscope.Generation.call(
        dashscope.Generation.Models.qwen_turbo,
        messages=messages,
        result_format='message',
        stream=True,
        incremental_output=True
    )

    for response in responses:
        # dashscope 的返回 item 可能是对象，以下按示例取字段
        try:
            if getattr(response, 'status_code', None) in (HTTPStatus.OK, 200):
                # 适配返回结构
                output = None
                if hasattr(response, 'output') and response.output:
                    output = response.output
                elif isinstance(response, dict):
                    output = response.get('output')

                if output:
                    # 尝试按常见结构取出增量文本
                    try:
                        content = output.choices[0]['message']['content']
                    except Exception:
                        content = str(output)
                    yield content
                else:
                    yield ''
            else:
                # 非 200 的情况
                code = getattr(response, 'code', '')
                message = getattr(response, 'message', '')
                yield f"Error: {code} - {message}"
        except Exception as e:
            yield f"Error processing response: {e}"


@app.post("/api/ai/chat")
async def chat_endpoint(request: ChatRequest):
    if not request.prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")
    
    return StreamingResponse(
        call_qwen_stream(request.prompt, request.context),
        media_type="text/event-stream"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
