# AI-RAG-Assistant

基于 RAG（Retrieval-Augmented Generation）的多文档智能问答系统。

支持上传 PDF、Word、Markdown、TXT 文档，自动完成解析、分块、向量化、索引、检索，并基于大模型生成带引用来源的回答。

## 核心特性

- **多格式文档解析**：PDF（PyMuPDF）、Word（python-docx）、Markdown（markdown-it-py）、TXT
- **三级检索优化**：bge-small-zh 向量检索 → bge-reranker 重排 → Query Rewrite 问题改写
- **引用追溯**：回答附带来源文档名、页码、片段、相似度
- **多轮对话**：支持会话上下文，自动消解代词歧义
- **文档摘要**：短文档单次摘要，长文档 map-reduce 分段摘要
- **多 LLM 切换**：DeepSeek / Qwen / OpenAI 一键切换（兼容 OpenAI 协议）
- **前后端分离**：FastAPI 后端 + Vue 3 前端
- **Docker 部署**：一键启动完整服务

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI + Uvicorn + Python 3.10+ |
| ORM | SQLAlchemy 2.0 |
| 数据库 | SQLite（开发）→ MySQL（生产） |
| 向量化 | sentence-transformers + bge-small-zh-v1.5 |
| 向量检索 | FAISS (faiss-cpu) |
| 重排 | FlagEmbedding + bge-reranker-base |
| LLM | OpenAI SDK（兼容 DeepSeek/Qwen/OpenAI） |
| 前端 | Vue 3 + Vite + Element Plus |
| 部署 | Docker + docker-compose |

## 快速开始

### 1. 环境准备

- Python 3.10+
- Node.js 18+（前端开发）
- 至少 4GB 可用内存（模型加载）

### 2. 后端启动

```bash
# 克隆项目
cd ai-rag-assistant

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY

# 初始化数据库
python scripts/init_db.py

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 API 文档：http://localhost:8000/docs

### 3. 前端启动

```bash
cd frontend
npm install
npm run dev
```

访问前端：http://localhost:5173

### 4. 首次使用

1. 首次启动时会自动下载 bge-small-zh 和 bge-reranker 模型（约 400MB）
2. 通过前端或 API 上传文档
3. 在问答页面提问

## Docker 部署

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f backend
```

服务端口：
- 后端 API：8000
- 前端：80

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /health | 健康检查 |
| POST | /api/upload | 上传文档 |
| GET | /api/documents | 文档列表 |
| GET | /api/documents/{id} | 文档详情 |
| DELETE | /api/documents/{id} | 删除文档 |
| POST | /api/summary/{id} | 生成摘要 |
| POST | /api/chat/session | 新建会话 |
| POST | /api/chat | 问答 |
| GET | /api/chat/session/{id} | 会话历史 |

详细接口说明访问 http://localhost:8000/docs

## 项目结构

```
ai-rag-assistant/
├─ app/                    # 后端主应用
│  ├─ api/                 # 路由层
│  ├─ core/                # 基础设施（日志、异常、响应）
│  ├─ models/              # 数据模型（ORM 实体 + Pydantic schema）
│  ├─ services/            # 业务编排层
│  ├─ parsers/             # 文档解析器
│  ├─ prompts/             # Prompt 模板
│  ├─ repositories/        # 数据访问层
│  ├─ utils/               # 工具函数
│  └─ db/                  # 数据库连接
├─ frontend/               # Vue 3 前端
├─ data/                   # 数据目录（上传、索引、DB）
├─ scripts/                # 运维脚本
├─ tests/                  # 测试
├─ .env.example            # 配置模板
├─ requirements.txt        # Python 依赖
├─ Dockerfile              # 后端镜像
└─ docker-compose.yml      # 编排配置
```

## 配置说明

所有配置通过 `.env` 文件管理，关键配置项：

| 配置 | 说明 | 默认值 |
|------|------|--------|
| LLM_PROVIDER | LLM 服务商 | deepseek |
| LLM_API_KEY | LLM API 密钥 | （必填） |
| LLM_BASE_URL | LLM 接口地址 | https://api.deepseek.com/v1 |
| LLM_MODEL | 模型名 | deepseek-chat |
| EMBEDDING_MODEL | 向量化模型 | BAAI/bge-small-zh-v1.5 |
| RERANK_ENABLED | 是否启用重排 | true |
| CHUNK_SIZE | 分块大小（token） | 512 |
| TOP_K_CANDIDATES | 向量检索候选数 | 10 |
| TOP_N_FINAL | 最终引用数 | 5 |

## 测试

```bash
# 运行单元测试
pytest tests/unit/ -v

# 运行集成测试（需要完整环境）
pytest tests/integration/ -v
```

## 开发计划

- [x] 阶段一：MVP（上传、解析、检索、问答）
- [x] 阶段二：多格式支持、文档管理、摘要、会话历史
- [x] 阶段三：Rerank、Query Rewrite、多轮对话
- [x] 阶段四：测试、Docker、文档

## License

MIT
