import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# ========================================================
# 1. 智能锁定路径 (关键修复)
# ========================================================
# __file__ 是当前脚本 (config.py) 的绝对路径
# .parent -> core/
# .parent -> app/
# .parent -> backend/  <-- .env 就在这里
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BACKEND_DIR / ".env"

# 调试打印 (让你运行脚本时一眼就能确认路径对不对)
print(f"\n[Config] 正在初始化配置...")
print(f"[Config] 锁定 .env 绝对路径: {ENV_PATH}")

if not ENV_PATH.exists():
    print(f"❌ [Config] 严重警告：在 {ENV_PATH} 未找到 .env 文件！请检查文件是否存在。")
else:
    print(f"✅ [Config] 成功检测到 .env 文件。")

# ========================================================
# 2. Settings 定义
# ========================================================
class Settings(BaseSettings):
    # --- 必填配置 ---
    # 如果 .env 里没有这个，程序会直接报错停止，防止后面瞎跑
    # DASHSCOPE_API_KEY: str  # Deprecated
    OPENAI_API_KEY: str
    DASHSCOPE_API_KEY: str | None = None # Keep for backward compatibility if needed
    
    # --- 可选配置 (带默认值) ---
    DASHSCOPE_API_URL: str | None = None
    OPENAI_API_BASE: str = "https://jeniya.top/v1"
    
    # 向量数据库配置
    MILVUS_HOST: str | None = None
    MILVUS_PORT: int | None = None
    RAG_COLLECTION: str | None = None

    # Database
    DATABASE_URL: str = "mysql+pymysql://cecraft_user:cecraft_password@localhost:3306/cecraft"

    # Security
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # 模型配置 (Scheme 3: Centralized Config)
    LLM_MODEL_LITE: str = "qwen-flash"   # 轻量级模型 (摘要、简单分类)
    LLM_MODEL_PRO: str = "qwen-flash"      # 专业级模型 (生成、推理、复杂指令)
    
    # 兼容旧配置 (指向 Lite 或 Pro 均可，这里指向 Pro 以保证默认质量)
    LLM_MODEL_NAME: str = "qwen-flash"
    EMBEDDING_MODEL_NAME: str = "text-embedding-v4"
    RERANK_MODEL_NAME: str = "qwen3-rerank"
    
    # Search Configuration
    SEARCH_PROVIDER: str = "bocha"  # Options: "duckduckgo", "bocha"
    BOCHA_API_KEY: str | None = None

    # Pydantic 配置
    model_config = SettingsConfigDict(
        # 核心修复点：强制使用计算出的【绝对路径】，而非默认的相对路径
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore"  # 忽略 .env 中多余的字段，防止报错
    )

# ========================================================
# 3. 实例化
# ========================================================
try:
    settings = Settings()
    # 为了安全，只打印 Key 的前几位
    masked_key = f"{settings.OPENAI_API_KEY[:4]}******" if settings.OPENAI_API_KEY else "None"
    print(f"✅ [Config] 配置加载成功 (Key: {masked_key})\n")
except Exception as e:
    print(f"💥 [Config] 配置加载崩溃: {e}")
    # 再次抛出异常，阻止程序继续运行
    raise e