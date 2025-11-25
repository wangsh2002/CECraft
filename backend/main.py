import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints import agent as agent_router

app = FastAPI(title="CECraft Agent API")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
# 注意：前端之前调用的是 /api/ai/review 和 /api/ai/agent
# 这里通过 prefix 统一配置，router 内部只需要写 /review 和 /agent
app.include_router(agent_router.router, prefix="/api/ai", tags=["AI Agent"])

if __name__ == "__main__":
    # 使用字符串加载方式，支持热重载
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)