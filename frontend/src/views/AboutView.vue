<template>
  <div class="about-view">
    <el-card>
      <template #header>
        <span style="font-weight: 600">系统信息</span>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="系统名称">AI 文档智能问答助手</el-descriptions-item>
        <el-descriptions-item label="版本">{{ health?.version || '-' }}</el-descriptions-item>
        <el-descriptions-item label="数据库状态">
          <el-tag :type="health?.db === 'connected' ? 'success' : 'danger'" size="small">
            {{ health?.db === 'connected' ? '已连接' : '未连接' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="FAISS 索引">
          <el-tag :type="health?.faiss_loaded ? 'success' : 'warning'" size="small">
            {{ health?.faiss_loaded ? '已加载' : '未加载' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>
        <span style="font-weight: 600">功能特性</span>
      </template>
      <ul class="feature-list">
        <li><el-icon color="#67c23a"><Check /></el-icon> 多格式文档解析（PDF / Word / Markdown / TXT）</li>
        <li><el-icon color="#67c23a"><Check /></el-icon> bge-small-zh 向量化 + FAISS 本地索引</li>
        <li><el-icon color="#67c23a"><Check /></el-icon> bge-reranker 二次重排，提升检索精度</li>
        <li><el-icon color="#67c23a"><Check /></el-icon> Query Rewrite 多轮对话问题改写</li>
        <li><el-icon color="#67c23a"><Check /></el-icon> 引用来源追溯（文档名 + 页码 + 相似度）</li>
        <li><el-icon color="#67c23a"><Check /></el-icon> 多 LLM 支持（DeepSeek / Qwen / OpenAI）</li>
        <li><el-icon color="#67c23a"><Check /></el-icon> 文档摘要生成（支持长文档分段摘要）</li>
        <li><el-icon color="#67c23a"><Check /></el-icon> 多轮对话上下文管理</li>
        <li><el-icon color="#67c23a"><Check /></el-icon> Docker 容器化部署</li>
      </ul>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>
        <span style="font-weight: 600">技术架构</span>
      </template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="后端框架">FastAPI + Uvicorn</el-descriptions-item>
        <el-descriptions-item label="ORM">SQLAlchemy 2.0</el-descriptions-item>
        <el-descriptions-item label="数据库">SQLite（开发）/ MySQL（生产）</el-descriptions-item>
        <el-descriptions-item label="向量检索">FAISS (faiss-cpu)</el-descriptions-item>
        <el-descriptions-item label="Embedding">bge-small-zh-v1.5</el-descriptions-item>
        <el-descriptions-item label="Rerank">bge-reranker-base</el-descriptions-item>
        <el-descriptions-item label="LLM 接入">OpenAI SDK（兼容协议）</el-descriptions-item>
        <el-descriptions-item label="前端框架">Vue 3 + Vite + Element Plus</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card style="margin-top: 16px">
      <template #header>
        <span style="font-weight: 600">使用指南</span>
      </template>
      <el-steps direction="vertical" :active="4">
        <el-step title="上传文档" description="进入文档管理页面，上传 PDF/Word/Markdown/TXT 文档，系统将自动解析、分块、向量化并建立索引" />
        <el-step title="开始问答" description="进入智能问答页面，输入问题，系统将检索相关文档片段并生成回答" />
        <el-step title="查看引用" description="回答下方会展示引用来源，点击可查看原文片段、文档名和页码" />
        <el-step title="多轮对话" description="在同一会话中继续追问，系统会自动改写问题并保留上下文" />
        <el-step title="生成摘要" description="在文档管理页面点击摘要按钮，快速了解文档核心内容" />
      </el-steps>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Check } from '@element-plus/icons-vue'
import { checkHealth } from '@/api/document'
import type { HealthStatus } from '@/types'

const health = ref<HealthStatus | null>(null)

onMounted(async () => {
  try {
    const resp = await checkHealth()
    health.value = resp.data.data
  } catch {
    // 后端未启动
  }
})
</script>

<style scoped>
.about-view {
  padding: 20px;
  max-width: 900px;
  margin: 0 auto;
}

.feature-list {
  list-style: none;
  padding: 0;
}

.feature-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 14px;
  color: #606266;
}
</style>
