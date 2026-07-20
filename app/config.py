"""应用配置管理。

使用 pydantic-settings 从 .env 加载配置，所有配置项集中在此处。
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置。从 .env 文件自动加载，字段名不区分大小写。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- 应用 ----
    APP_NAME: str = "AI-RAG-Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ---- 数据库 ----
    DATABASE_URL: str = "sqlite:///data/app.db"

    # ---- 文件存储 ----
    UPLOAD_DIR: str = "data/uploads"
    PROCESSED_DIR: str = "data/processed"
    FAISS_INDEX_DIR: str = "data/faiss_index"
    MAX_FILE_SIZE_MB: int = 50

    # ---- 分块 ----
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 50

    # ---- 检索 ----
    TOP_K_CANDIDATES: int = 10
    TOP_N_FINAL: int = 5
    SIMILARITY_THRESHOLD: float = 0.3
    HISTORY_TURNS: int = 3

    # ---- 问答模式 ----
    # 默认问答模式：strict | open
    DEFAULT_CHAT_MODE: str = "open"
    # 严格模式检索参数（top_k 偏小、阈值更高，避免引入无关上下文）
    STRICT_MODE_TOP_K: int = 8
    STRICT_MODE_TOP_N: int = 3
    STRICT_SIMILARITY_THRESHOLD: float = 0.45
    # 严格模式：候选数不足或最高分低于阈值时直接拒答
    STRICT_MIN_HITS: int = 1
    # 开放模式检索参数（top_k 略大，允许更多上下文以便模型解释）
    OPEN_MODE_TOP_K: int = 12
    OPEN_MODE_TOP_N: int = 5
    OPEN_SIMILARITY_THRESHOLD: float = 0.3
    # ---- 答案支持性校验（verifier），仅在严格模式下默认启用 ----
    VERIFIER_ENABLED: bool = True
    # Verifier 是否使用 JSON Mode（强制结构化输出，避免正则解析失败）
    VERIFIER_JSON_MODE: bool = True

    # ---- Context Window 管理 ----
    # 单次问答 Context 最大 token 数（含历史）；超出时按相关性截断检索片段
    CONTEXT_MAX_TOKENS: int = 6000
    # 历史对话占用 token 预算上限
    HISTORY_MAX_TOKENS: int = 1500

    # ---- 检索增强：多路召回与查询扩展 ----
    # Multi-Query Retrieval：LLM 生成多个变种问题，分别检索后并集 rerank
    MULTI_QUERY_ENABLED: bool = True
    MULTI_QUERY_COUNT: int = 3  # 生成的变种问题数
    # HyDE（Hypothetical Document Embeddings）：先让 LLM 生成假设性答案再检索
    HYDE_ENABLED: bool = False  # 默认关闭，HyDE 会额外消耗一次 LLM 调用

    # ---- 语义缓存 ----
    SEMANTIC_CACHE_ENABLED: bool = True
    # 命中阈值：query 向量相似度 >= 该值时直接返回缓存答案
    SEMANTIC_CACHE_THRESHOLD: float = 0.98
    # 缓存最大条目数（LRU 淘汰）
    SEMANTIC_CACHE_MAX_SIZE: int = 200

    # ---- SSE 流式输出 ----
    SSE_ENABLED: bool = True

    # ---- Embedding ----
    EMBEDDING_MODEL: str = "models/bge-small-zh-v1.5"  # 本地路径，避免 HF 下载问题
    EMBEDDING_DEVICE: str = "cpu"

    # ---- Rerank ----
    RERANK_MODEL: str = "models/bge-reranker-base"  # 本地路径
    RERANK_DEVICE: str = "cpu"
    RERANK_ENABLED: bool = True

    # ---- HuggingFace 镜像（国内下载模型用） ----
    HF_ENDPOINT: str = "https://hf-mirror.com"

    # ---- LLM ----
    LLM_PROVIDER: str = "deepseek"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_MODEL: str = "deepseek-chat"
    LLM_TIMEOUT: int = 120
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.3

    # ---- 日志 ----
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs"

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def supported_file_types(self) -> tuple[str, ...]:
        return ("pdf", "docx", "md", "txt")

    def ensure_dirs(self) -> None:
        """确保所有运行时目录存在。"""
        for d in (self.UPLOAD_DIR, self.PROCESSED_DIR, self.FAISS_INDEX_DIR, self.LOG_DIR):
            Path(d).mkdir(parents=True, exist_ok=True)


settings = Settings()
