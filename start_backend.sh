#!/bin/bash

# 获取脚本所在目录，确保在项目根目录执行
# 否则 app/config.py 中 env_file=".env" 相对路径解析失败 -> LLM_API_KEY 为空 -> 网关返回 401
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Starting backend server..."
echo "Press Ctrl+C to stop the server."

# 使用系统 Python 3.12（已装全套 ML 依赖：sentence_transformers/faiss/FlagEmbedding/PyMuPDF/python-docx）
PYTHON="/c/Users/Lenovo/AppData/Local/Programs/Python/Python312/python.exe"

# 必须用 --host 127.0.0.1（IPv4），不要用 localhost（Node Happy Eyeballs 会解析到 IPv6 导致 ECONNREFUSED）
# 端口必须是 8088，与 frontend/vite.config.ts 的 proxy target 一致
"$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8088 --reload
