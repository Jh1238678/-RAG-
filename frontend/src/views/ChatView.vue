<template>
  <div class="chat-view">
    <!-- 左侧：会话列表 -->
    <div class="session-sidebar">
      <div class="session-header">
        <button class="new-session-btn" @click="newSession">
          <el-icon><Plus /></el-icon>
          <span>新建对话</span>
        </button>
      </div>
      <div class="session-list">
        <div
          v-for="session in chatStore.sessions"
          :key="session.id"
          class="session-item"
          :class="{ active: session.id === chatStore.currentSessionId }"
          @click="switchSession(session.id)"
          @dblclick="startRename(session)"
        >
          <el-icon class="session-icon"><ChatDotSquare /></el-icon>

          <!-- 重命名输入框 -->
          <input
            v-if="renamingId === session.id"
            ref="renameInputRef"
            v-model="renamingTitle"
            class="rename-input"
            @click.stop
            @keydown.enter="confirmRename(session.id)"
            @keydown.escape="cancelRename"
            @blur="confirmRename(session.id)"
          />
          <span v-else class="session-title">{{ session.title }}</span>

          <!-- 操作按钮组 -->
          <div class="session-actions" v-if="renamingId !== session.id">
            <el-icon
              class="session-action-btn rename-btn"
              title="重命名（双击标题也可）"
              @click.stop="startRename(session)"
            >
              <Edit />
            </el-icon>
            <el-icon
              class="session-action-btn delete-btn"
              title="删除会话"
              @click.stop="confirmDeleteSession(session.id, session.title)"
            >
              <Close />
            </el-icon>
          </div>
        </div>
        <el-empty v-if="chatStore.sessions.length === 0" description="点击新建对话开始" :image-size="60" />
      </div>

      <!-- 文档检索范围 -->
      <div class="doc-filter">
        <div class="filter-header" @click="filterExpanded = !filterExpanded">
          <span>检索范围</span>
          <el-icon><ArrowDown v-if="!filterExpanded" /><ArrowUp v-else /></el-icon>
        </div>
        <div v-show="filterExpanded" class="filter-body">
          <div v-if="chatStore.selectedDocumentIds.length === 0" class="filter-empty">
            全部文档
          </div>
          <el-tag
            v-for="docId in chatStore.selectedDocumentIds"
            :key="docId"
            closable
            size="small"
            @close="chatStore.toggleDocumentFilter(docId)"
            style="margin: 2px"
          >
            {{ getDocName(docId) }}
          </el-tag>
        </div>
      </div>
    </div>

    <!-- 右侧：对话区 -->
    <div class="chat-main">
      <!-- 消息列表 -->
      <div class="message-list" ref="messageListRef">
        <template v-if="currentSession && currentSession.messages.length > 0">
          <div
            v-for="message in currentSession.messages"
            :key="message.id"
            class="message-item"
            :class="message.role"
          >
            <div class="message-avatar">
              <el-icon v-if="message.role === 'user'" size="20"><User /></el-icon>
              <el-icon v-else size="20"><Robot /></el-icon>
            </div>
            <div class="message-body">
              <div class="message-role">
                {{ message.role === 'user' ? '我' : 'AI 助手' }}
                <!-- 模式标签 -->
                <el-tag
                  v-if="message.role === 'assistant' && (message as any).mode"
                  size="small"
                  :type="(message as any).mode === 'strict' ? 'danger' : 'success'"
                  effect="plain"
                  class="mode-tag"
                >
                  {{ (message as any).mode === 'strict' ? '严格' : '开放' }}
                </el-tag>
                <!-- 严格模式 grounded 标识 -->
                <el-tag
                  v-if="message.role === 'assistant' && (message as any).mode === 'strict' && (message as any).grounded !== null && (message as any).grounded !== undefined"
                  size="small"
                  :type="(message as any).grounded ? 'success' : 'warning'"
                  effect="dark"
                  class="grounded-tag"
                >
                  {{ (message as any).grounded ? '有据可查' : '证据不足' }}
                </el-tag>
                <!-- 开放模式补充说明标识 -->
                <el-tag
                  v-if="message.role === 'assistant' && (message as any).mode === 'open' && (message as any).supplement_note"
                  size="small"
                  type="info"
                  effect="plain"
                  class="grounded-tag"
                >
                  含补充说明
                </el-tag>
              </div>
              <!-- 严格模式拒答原因 -->
              <div
                v-if="message.role === 'assistant' && (message as any).unsupported_reason"
                class="unsupported-reason"
              >
                <el-icon><WarningFilled /></el-icon>
                <span>拒答原因：{{ (message as any).unsupported_reason }}</span>
                <!-- 拒答引导：切换到开放模式 -->
                <el-button
                  v-if="(message as any).mode === 'strict'"
                  size="small"
                  type="primary"
                  plain
                  class="retry-open-btn"
                  @click="retryInOpenMode"
                >
                  切换到开放模式重试
                </el-button>
              </div>
              <!-- 缓存命中标识 -->
              <div
                v-if="message.role === 'assistant' && (message as any).from_cache"
                class="cache-hit-badge"
              >
                <el-icon><Lightning /></el-icon>
                <span>缓存命中（毫秒级响应）</span>
              </div>
              <!-- 改写后的 query -->
              <div v-if="message.rewritten_query" class="rewritten-query">
                <el-icon><Refresh /></el-icon>
                <span>改写后：{{ message.rewritten_query }}</span>
              </div>
              <!-- 消息内容：开放模式补充说明高亮 -->
              <div
                v-if="message.role === 'assistant'"
                class="message-content markdown-body"
                v-html="renderMarkdownWithSupplement(message.content, (message as any).mode)"
              ></div>
              <div v-else class="message-content">{{ message.content }}</div>
              <!-- Verifier 校验结果（严格模式） -->
              <div
                v-if="message.role === 'assistant' && (message as any).verifier_result"
                class="verifier-result"
              >
                <div class="verifier-header">
                  <el-icon><CircleCheck v-if="(message as any).verifier_result.verdict === 'supported'" /><Warning v-else-if="(message as any).verifier_result.verdict === 'partial'" /><CircleClose v-else /></el-icon>
                  <span>答案校验：{{ verifierLabel((message as any).verifier_result.verdict) }}</span>
                </div>
                <div v-if="(message as any).verifier_result.reason" class="verifier-reason">
                  {{ (message as any).verifier_result.reason }}
                </div>
                <div
                  v-if="(message as any).verifier_result.unsupported_spans && (message as any).verifier_result.unsupported_spans.length > 0"
                  class="verifier-spans"
                >
                  <span class="spans-label">未被支持的表述：</span>
                  <el-tag
                    v-for="(span, idx) in (message as any).verifier_result.unsupported_spans"
                    :key="idx"
                    size="small"
                    type="warning"
                    style="margin: 2px"
                  >{{ span }}</el-tag>
                </div>
              </div>
              <!-- 引用来源 -->
              <div v-if="message.source_chunks && message.source_chunks.length > 0" class="sources">
                <div class="sources-title">
                  <el-icon><Link /></el-icon>
                  引用来源（{{ message.source_chunks.length }}）
                </div>
                <el-collapse>
                  <el-collapse-item
                    v-for="(source, idx) in message.source_chunks"
                    :key="source.chunk_id"
                    :name="idx"
                  >
                    <template #title>
                      <span class="source-header">
                        <el-tag size="small" type="info">[{{ idx + 1 }}]</el-tag>
                        {{ source.document_name }}
                        <span v-if="source.page_num" class="source-page">第 {{ source.page_num }} 页</span>
                        <span class="source-score">{{ (source.score * 100).toFixed(1) }}%</span>
                      </span>
                    </template>
                    <div class="source-snippet">{{ source.snippet }}</div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>
          </div>
        </template>

        <!-- 空状态 -->
        <div v-else class="empty-chat">
          <div class="empty-icon">
            <el-icon size="56"><ChatLineSquare /></el-icon>
          </div>
          <p class="empty-title">开始与 AI 文档助手对话</p>
          <p class="empty-desc">上传文档后，在此提问即可获得带引用来源的回答</p>
        </div>

        <!-- 加载中 -->
        <div v-if="chatStore.sending && currentSession" class="message-item assistant">
          <div class="message-avatar">
            <el-icon size="20"><Robot /></el-icon>
          </div>
          <div class="message-body">
            <div class="message-role">AI 助手</div>
            <div class="message-content typing">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="input-area">
        <div class="input-left">
          <!-- 问答模式切换 -->
          <div class="mode-switcher">
            <el-radio-group v-model="chatStore.chatMode" size="small" @change="onModeChange">
              <el-radio-button label="open">开放模式</el-radio-button>
              <el-radio-button label="strict">严格模式</el-radio-button>
            </el-radio-group>
            <el-tooltip
              :content="chatStore.chatMode === 'strict'
                ? '严格模式：仅依据文档回答，不允许外推；证据不足时会拒答'
                : '开放模式：基于文档回答，允许适度解释和补充说明'"
              placement="top"
            >
              <el-icon class="mode-help"><QuestionFilled /></el-icon>
            </el-tooltip>
          </div>
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="2"
            placeholder="输入你的问题...（Enter 发送，Shift+Enter 换行）"
            resize="none"
            @keydown.enter.exact.prevent="send"
            :disabled="chatStore.sending"
          />
        </div>
        <el-button
          type="primary"
          :icon="Promotion"
          @click="send"
          :loading="chatStore.sending"
          :disabled="!inputText.trim()"
          class="send-btn"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, watch } from 'vue'
import {
  Plus, User, Promotion, Refresh, Link, ArrowDown, ArrowUp,
  QuestionFilled, WarningFilled, CircleCheck, CircleClose, Warning, Close, Edit
} from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { useChatStore } from '@/stores/chat'
import { useDocumentStore } from '@/stores/document'
import type { ChatMode } from '@/types'
import type { Session } from '@/stores/chat'

// 自定义 Lightning 图标（缓存命中）
const Lightning = {
  template: '<svg viewBox="0 0 1024 1024" width="1em" height="1em"><path fill="currentColor" d="M548 199.7c-7.6-23-37.4-29.4-53.8-11.1L183.6 535.5c-13.2 14.7-8.7 38.1 8.9 47.9l193.4 108.2-83.2 203.2c-7.6 23 9.8 46.8 33.9 46.8 8.4 0 16.7-3.2 23-9.6L755 568.7c13.2-14.7 8.7-38.1-8.9-47.9L552.7 412.6l83.2-203.2c1.9-3.3 2.9-6.9 2.9-10.7 0-3.5-1-6.9-2.9-10.1z"/></svg>'
}

// 自定义图标（Element Plus 没有 Robot 图标，用 Service 代替）
const Robot = {
  template: '<svg viewBox="0 0 1024 1024" width="1em" height="1em"><path fill="currentColor" d="M512 128c-141.389 0-256 114.611-256 256v128H192a32 32 0 0 0-32 32v320a32 32 0 0 0 32 32h640a32 32 0 0 0 32-32V544a32 32 0 0 0-32-32h-64V384c0-141.389-114.611-256-256-256zm-128 384V384a128 128 0 0 1 256 0v128H384zm192 96v96a32 32 0 1 1-64 0v-96a32 32 0 1 1 64 0z"/></svg>'
}
const ChatDotSquare = { template: '<svg viewBox="0 0 1024 1024" width="1em" height="1em"><path fill="currentColor" d="M192 128h640a64 64 0 0 1 64 64v448a64 64 0 0 1-64 64H320l-192 128V192a64 64 0 0 1 64-64z"/></svg>' }
const ChatLineSquare = ChatDotSquare

const chatStore = useChatStore()
const docStore = useDocumentStore()

const inputText = ref('')
const messageListRef = ref<HTMLElement>()
const filterExpanded = ref(true)

// 重命名相关状态
const renamingId = ref<string | null>(null)
const renamingTitle = ref('')
const renameInputRef = ref<HTMLInputElement>()

const currentSession = computed(() => chatStore.getCurrentSession())

// 加载文档列表（用于检索范围选择）
if (docStore.documents.length === 0) {
  docStore.fetchDocuments({ page: 1, page_size: 100 })
}

// 启动时加载后端历史会话列表
chatStore.loadSessions().then(() => {
  if (chatStore.sessions.length === 0) {
    chatStore.createNewSession()
  } else if (!chatStore.currentSessionId) {
    const first = chatStore.sessions[0]
    chatStore.switchSession(first.id)
    if (!first.id.startsWith('temp-') && first.messages.length === 0) {
      chatStore.loadSessionHistory(first.id)
    }
  }
})

function getDocName(docId: string): string {
  const doc = docStore.documents.find(d => d.id === docId)
  return doc ? doc.file_name : docId.slice(0, 8)
}

function newSession() {
  chatStore.createNewSession()
}

function switchSession(sessionId: string) {
  chatStore.switchSession(sessionId)
  const session = chatStore.sessions.find(s => s.id === sessionId)
  if (session && !sessionId.startsWith('temp-') && session.messages.length === 0) {
    chatStore.loadSessionHistory(sessionId)
  }
}

/** 开始重命名会话 */
function startRename(session: Session) {
  renamingId.value = session.id
  renamingTitle.value = session.title === '新对话' ? '' : session.title
  nextTick(() => {
    renameInputRef.value?.focus()
    renameInputRef.value?.select()
  })
}

/** 确认重命名 */
async function confirmRename(sessionId: string) {
  if (renamingId.value !== sessionId) return
  const newTitle = renamingTitle.value.trim()
  if (!newTitle) {
    cancelRename()
    return
  }
  const session = chatStore.sessions.find(s => s.id === sessionId)
  if (session && session.title !== newTitle) {
    const ok = await chatStore.renameSession(sessionId, newTitle)
    if (ok) {
      ElMessage.success('已重命名')
    } else {
      ElMessage.error('重命名失败，请重试')
    }
  }
  renamingId.value = null
  renamingTitle.value = ''
}

/** 取消重命名 */
function cancelRename() {
  renamingId.value = null
  renamingTitle.value = ''
}

/** 删除会话前确认，避免误删。 */
function confirmDeleteSession(sessionId: string, title?: string) {
  const displayTitle = title && title !== '新对话' ? `「${title}」` : '该会话'
  ElMessageBox.confirm(
    `确定要删除${displayTitle}吗？会话内的所有消息将一并删除，且无法恢复。`,
    '删除会话',
    {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      confirmButtonClass: 'el-button--danger'
    }
  ).then(async () => {
    const ok = await chatStore.deleteSession(sessionId)
    if (ok) {
      ElMessage.success('会话已删除')
    } else {
      ElMessage.error('删除失败，请重试')
    }
  }).catch(() => {
    // 用户取消
  })
}

async function send() {
  if (!inputText.value.trim() || chatStore.sending) return
  const question = inputText.value
  inputText.value = ''
  await chatStore.sendMessage(question)
  scrollToBottom()
}

function onModeChange(val: ChatMode | string | number | boolean | undefined) {
  chatStore.setChatMode(val as ChatMode)
}

function verifierLabel(verdict: string): string {
  switch (verdict) {
    case 'supported': return '证据充分支持'
    case 'partial': return '部分被支持'
    case 'unsupported': return '未被证据支持'
    default: return verdict
  }
}

function renderMarkdown(content: string): string {
  if (!content) return '<span style="color:#94a3b8">（生成中...）</span>'
  const html = marked.parse(content)
  const htmlStr = typeof html === 'string' ? html : ''
  return DOMPurify.sanitize(htmlStr)
}

/**
 * 开放模式：将"补充说明"段落高亮显示（特殊背景框），
 * 严格模式：正常渲染
 */
function renderMarkdownWithSupplement(content: string, mode?: string): string {
  if (!content) return '<span style="color:#94a3b8">（生成中...）</span>'
  const html = marked.parse(content)
  const htmlStr = typeof html === 'string' ? html : ''
  let sanitized = DOMPurify.sanitize(htmlStr)

  // 开放模式：把"补充说明"段落包成高亮 div
  if (mode === 'open') {
    sanitized = sanitized.replace(
      /<(h[2-4])[^>]*>\s*补充说明[\s\S]*?<\/\1>([\s\S]*?)(?=<h[2-4]|$)/g,
      (_match, _tag, body) => {
        return `<div class="supplement-block">
          <div class="supplement-header">AI 补充说明（非文档原文）</div>
          <div class="supplement-body">${body}</div>
        </div>`
      }
    )
  }

  return sanitized
}

/** 严格模式拒答时，切换到开放模式并自动重发上一问题 */
function retryInOpenMode() {
  chatStore.setChatMode('open')
  const session = currentSession.value
  if (!session) return
  const lastUser = [...session.messages].reverse().find(m => m.role === 'user')
  if (lastUser && lastUser.content) {
    const lastAssistantIdx = session.messages.length - 1
    if (session.messages[lastAssistantIdx]?.role === 'assistant') {
      session.messages.splice(lastAssistantIdx, 1)
    }
    sendWithQuestion(lastUser.content)
  }
}

async function sendWithQuestion(question: string) {
  if (chatStore.sending) return
  await chatStore.sendMessage(question)
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (messageListRef.value) {
      messageListRef.value.scrollTop = messageListRef.value.scrollHeight
    }
  })
}

// 监听消息变化，自动滚动
watch(
  () => currentSession.value?.messages.length,
  () => scrollToBottom()
)
</script>

<style scoped>
/* ==================== Indigo SaaS 设计系统变量 ==================== */
.chat-view {
  /* 主色 */
  --indigo-50: #EEF2FF;
  --indigo-100: #E0E7FF;
  --indigo-200: #C7D2FE;
  --indigo-400: #818CF8;
  --indigo-500: #6366F1;
  --indigo-600: #4F46E5;
  --indigo-700: #4338CA;
  --indigo-800: #3730A3;
  --indigo-900: #312E81;
  --indigo-950: #1E1B4B;
  /* Emerald CTA */
  --emerald-400: #34D399;
  --emerald-500: #10B981;
  --emerald-600: #059669;
  /* 中性色 */
  --slate-50: #F8FAFC;
  --slate-100: #F1F5F9;
  --slate-200: #E2E8F0;
  --slate-300: #CBD5E1;
  --slate-400: #94A3B8;
  --slate-500: #64748B;
  --slate-600: #475569;
  --slate-700: #334155;
  --slate-800: #1E293B;
  --slate-900: #0F172A;
  /* 语义色 */
  --bg-sidebar: #1E1B4B;       /* 深色 Indigo 侧栏 */
  --bg-page: #F5F3FF;          /* 紫调页面背景 */
  --bg-card: #FFFFFF;          /* 卡片白 */
  --bg-hover: #EEF2FF;         /* 悬停浅紫 */
  --text-primary: #1E1B4B;     /* 深紫黑文字 */
  --text-secondary: #6366F1;   /* 次级文字 */
  --text-muted: #94A3B8;       /* 弱化文字 */
  --border-color: #E2E8F0;     /* 边框 */
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --radius-xl: 18px;

  display: flex;
  height: 100%;
  background: var(--bg-page);
  font-family: -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
}

/* ==================== 会话侧边栏 ==================== */
.session-sidebar {
  width: 260px;
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  background: var(--bg-sidebar);
  color: #C7D2FE;
}

.session-header {
  padding: 16px 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.new-session-btn {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  background: var(--indigo-500);
  color: #FFF;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.new-session-btn:hover {
  background: var(--indigo-400);
  transform: translateY(-1px);
}

.new-session-btn:active {
  transform: translateY(0);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 10px 8px;
}

/* 自定义滚动条 */
.session-list::-webkit-scrollbar,
.message-list::-webkit-scrollbar {
  width: 6px;
}

.session-list::-webkit-scrollbar-thumb,
.message-list::-webkit-scrollbar-thumb {
  background: var(--slate-300);
  border-radius: 3px;
}

.session-list::-webkit-scrollbar-track,
.message-list::-webkit-scrollbar-track {
  background: transparent;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 12px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.2s;
  color: #A5B4FC;
  margin-bottom: 2px;
  position: relative;
}

.session-item:hover {
  background: rgba(99, 102, 241, 0.15);
  color: #E0E7FF;
}

.session-item.active {
  background: rgba(99, 102, 241, 0.25);
  color: #FFFFFF;
  border-left: 3px solid var(--indigo-400);
  padding-left: 9px;
}

.session-icon {
  flex-shrink: 0;
  font-size: 16px;
}

.session-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 400;
}

/* 重命名输入框 */
.rename-input {
  flex: 1;
  min-width: 0;
  background: var(--slate-50);
  border: 1px solid var(--indigo-400);
  border-radius: var(--radius-sm);
  padding: 4px 8px;
  font-size: 13px;
  color: var(--text-primary);
  outline: none;
}

.session-actions {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.2s;
}

.session-item:hover .session-actions {
  opacity: 1;
}

.session-item.active .session-actions {
  opacity: 0.9;
}

.session-action-btn {
  padding: 4px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.rename-btn:hover {
  color: var(--indigo-400);
  background: rgba(99, 102, 241, 0.2);
}

.delete-btn:hover {
  color: #F87171;
  background: rgba(248, 113, 113, 0.2);
}

.session-item.active .rename-btn:hover,
.session-item.active .delete-btn:hover {
  color: #FFF;
}

/* 检索范围 */
.doc-filter {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 12px 14px;
}

.filter-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 12px;
  color: #818CF8;
  cursor: pointer;
  padding: 4px 0;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.filter-body {
  margin-top: 8px;
  min-height: 24px;
}

.filter-empty {
  color: #6366F1;
  font-size: 12px;
  opacity: 0.7;
}

/* ==================== 对话主区 ==================== */
.chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--bg-page);
}

.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

.message-item {
  display: flex;
  gap: 14px;
  margin-bottom: 28px;
  max-width: 900px;
}

.message-item.user {
  flex-direction: row-reverse;
}

.message-item.user .message-body {
  align-items: flex-end;
}

.message-avatar {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--indigo-500);
  color: #FFF;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);
}

.message-item.user .message-avatar {
  background: var(--emerald-500);
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.25);
}

.message-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.message-role {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.message-content {
  background: var(--bg-card);
  padding: 14px 18px;
  border-radius: var(--radius-lg);
  line-height: 1.75;
  word-wrap: break-word;
  font-size: 14px;
  color: var(--text-primary);
  border: 1px solid var(--border-color);
  box-shadow: 0 1px 3px rgba(99, 102, 241, 0.06);
}

.message-item.user .message-content {
  background: var(--indigo-100);
  color: var(--indigo-900);
  border-color: var(--indigo-200);
}

/* Markdown 内容美化 */
.message-content :deep(h1),
.message-content :deep(h2),
.message-content :deep(h3) {
  color: var(--indigo-900);
  font-weight: 600;
  margin: 12px 0 8px;
}

.message-content :deep(h1) { font-size: 18px; }
.message-content :deep(h2) { font-size: 16px; }
.message-content :deep(h3) { font-size: 15px; }

.message-content :deep(p) {
  margin: 8px 0;
}

.message-content :deep(ul),
.message-content :deep(ol) {
  padding-left: 20px;
  margin: 8px 0;
}

.message-content :deep(code) {
  background: var(--slate-100);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: var(--indigo-700);
  font-family: 'JetBrains Mono', 'Consolas', monospace;
}

.message-content :deep(pre) {
  background: var(--slate-900);
  color: var(--slate-100);
  padding: 12px 16px;
  border-radius: var(--radius-md);
  overflow-x: auto;
  margin: 8px 0;
}

.message-content :deep(pre code) {
  background: transparent;
  color: inherit;
  padding: 0;
}

.message-content :deep(blockquote) {
  border-left: 3px solid var(--indigo-400);
  padding-left: 12px;
  color: var(--slate-600);
  margin: 8px 0;
}

.message-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}

.message-content :deep(th),
.message-content :deep(td) {
  border: 1px solid var(--border-color);
  padding: 8px 12px;
  text-align: left;
}

.message-content :deep(th) {
  background: var(--slate-50);
  font-weight: 600;
}

/* 模式与校验标签 */
.mode-tag,
.grounded-tag {
  margin-left: 4px;
}

.rewritten-query {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #D97706;
  background: #FEF3C7;
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  width: fit-content;
}

.unsupported-reason {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #D97706;
  background: #FEF3C7;
  padding: 6px 10px;
  border-radius: var(--radius-sm);
  flex-wrap: wrap;
  border: 1px solid #FDE68A;
}

.retry-open-btn {
  margin-left: 8px;
}

.cache-hit-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #7C3AED;
  background: #EDE9FE;
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  width: fit-content;
  border: 1px solid #DDD6FE;
}

/* 补充说明高亮块 */
.supplement-block {
  margin: 12px 0;
  padding: 12px 16px;
  background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%);
  border-left: 4px solid #F59E0B;
  border-radius: var(--radius-md);
}

.supplement-header {
  font-size: 13px;
  font-weight: 600;
  color: #92400E;
  margin-bottom: 6px;
}

.supplement-body {
  font-size: 14px;
  color: #78350F;
  line-height: 1.7;
}

/* Verifier 校验结果 */
.verifier-result {
  margin-top: 8px;
  border: 1px solid var(--indigo-200);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  background: var(--indigo-50);
  font-size: 12px;
  color: var(--slate-700);
}

.verifier-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--indigo-600);
  font-weight: 600;
}

.verifier-reason {
  margin-top: 6px;
  color: var(--slate-600);
  line-height: 1.6;
}

.verifier-spans {
  margin-top: 8px;
}

.spans-label {
  color: var(--slate-500);
  margin-right: 4px;
}

/* 引用来源 */
.sources {
  margin-top: 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 10px;
  background: var(--bg-card);
}

.sources-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--indigo-600);
  font-weight: 600;
  margin-bottom: 6px;
}

.source-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--slate-700);
}

.source-page {
  color: var(--text-muted);
  font-size: 12px;
}

.source-score {
  color: var(--emerald-600);
  font-size: 12px;
  margin-left: auto;
  font-weight: 600;
}

.source-snippet {
  background: var(--slate-50);
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.7;
  color: var(--slate-700);
  margin-top: 6px;
  border-left: 3px solid var(--indigo-200);
}

/* 空状态 */
.empty-chat {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.empty-icon {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: var(--indigo-50);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--indigo-400);
  margin-bottom: 20px;
}

.empty-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--indigo-900);
  margin: 0 0 8px;
}

.empty-desc {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
  text-align: center;
  max-width: 400px;
  line-height: 1.6;
}

/* ==================== 输入区 ==================== */
.input-area {
  border-top: 1px solid var(--border-color);
  padding: 14px 24px 18px;
  display: flex;
  gap: 12px;
  align-items: flex-end;
  background: var(--bg-card);
}

.input-area :deep(.el-textarea__inner) {
  flex: 1;
  resize: none;
  border-radius: var(--radius-md);
  border-color: var(--border-color);
  transition: border-color 0.2s;
}

.input-area :deep(.el-textarea__inner:focus) {
  border-color: var(--indigo-400);
  box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.15);
}

.input-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.mode-switcher {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mode-switcher :deep(.el-radio-button__inner) {
  border-radius: 0;
  border-color: var(--border-color);
  color: var(--slate-600);
}

.mode-switcher :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: var(--indigo-500);
  border-color: var(--indigo-500);
  color: #FFF;
  box-shadow: -1px 0 0 0 var(--indigo-500);
}

.mode-help {
  color: var(--text-muted);
  cursor: help;
  font-size: 16px;
}

.send-btn {
  height: 64px;
  background: var(--indigo-500);
  border-color: var(--indigo-500);
  border-radius: var(--radius-md);
  font-weight: 500;
  transition: all 0.2s;
}

.send-btn:hover {
  background: var(--indigo-400);
  border-color: var(--indigo-400);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.send-btn:disabled {
  background: var(--slate-300);
  border-color: var(--slate-300);
}

/* ==================== 打字动画 ==================== */
.typing {
  display: flex;
  gap: 5px;
  align-items: center;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
}

.dot {
  width: 8px;
  height: 8px;
  background: var(--indigo-400);
  border-radius: 50%;
  animation: typing 1.4s infinite;
}

.dot:nth-child(2) { animation-delay: 0.2s; }
.dot:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: translateY(0); }
  30% { opacity: 1; transform: translateY(-5px); }
}

/* 响应式 */
@media (max-width: 768px) {
  .session-sidebar {
    width: 200px;
  }
  .message-list {
    padding: 16px;
  }
  .input-area {
    padding: 12px 16px;
  }
}
</style>
