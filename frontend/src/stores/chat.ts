import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Message, ChatResponse, ChatMode } from '@/types'
import * as chatApi from '@/api/chat'

export interface Session {
  id: string
  title: string
  messages: Message[]
  loading: boolean
}

export interface AssistantExtra {
  /** 本次问答使用的模式 */
  mode?: ChatMode
  /** 严格模式：答案是否被证据充分支持 */
  grounded?: boolean | null
  /** 严格模式：未命中拒答原因 */
  unsupported_reason?: string | null
  /** 开放模式：补充说明标识 */
  supplement_note?: string | null
  /** 严格模式可选：答案校验结果 */
  verifier_result?: {
    verdict: 'supported' | 'partial' | 'unsupported'
    reason?: string | null
    unsupported_spans: string[]
  } | null
  /** 是否来自语义缓存 */
  from_cache?: boolean
}

export const useChatStore = defineStore('chat', () => {
  const sessions = ref<Session[]>([])
  const currentSessionId = ref<string | null>(null)
  const sending = ref(false)

  // 选中的检索范围（文档 ID）
  const selectedDocumentIds = ref<string[]>([])

  // 当前问答模式，默认 open
  const chatMode = ref<ChatMode>('open')

  function getCurrentSession(): Session | null {
    if (!currentSessionId.value) return null
    return sessions.value.find(s => s.id === currentSessionId.value) || null
  }

  function createNewSession(title?: string): Session {
    const session: Session = {
      id: 'temp-' + Date.now(),
      title: title || '新对话',
      messages: [],
      loading: false
    }
    sessions.value.unshift(session)
    currentSessionId.value = session.id
    return session
  }

  function switchSession(sessionId: string) {
    currentSessionId.value = sessionId
  }

  function setChatMode(mode: ChatMode) {
    chatMode.value = mode
  }

  async function sendMessage(question: string) {
    if (!question.trim() || sending.value) return

    sending.value = true

    // 确保有会话
    let session = getCurrentSession()
    if (!session) {
      session = createNewSession()
    }

    // 添加 user 消息
    const userMsg: Message = {
      id: 'temp-' + Date.now(),
      role: 'user',
      content: question,
      created_at: new Date().toISOString()
    }
    session.messages.push(userMsg)

    // 添加占位 assistant 消息，附带模式信息占位
    const assistantMsg: Message & AssistantExtra = {
      id: 'temp-' + Date.now() + 1,
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      mode: chatMode.value
    }
    session.messages.push(assistantMsg)

    try {
      await chatApi.chatStream(
        {
          question,
          session_id: session.id.startsWith('temp-') ? undefined : session.id,
          document_ids: selectedDocumentIds.value.length > 0 ? selectedDocumentIds.value : undefined,
          mode: chatMode.value
        },
        (event) => {
          if (event.type === 'meta') {
            // 首次问答更新真实 session_id
            if (session!.id.startsWith('temp-')) {
              session!.id = event.session_id
              currentSessionId.value = event.session_id
            }
            // 更新标题
            if (session!.title === '新对话') {
              session!.title = question.slice(0, 20) + (question.length > 20 ? '...' : '')
            }
            assistantMsg.mode = event.mode
            assistantMsg.rewritten_query = event.rewritten_query
            if (event.from_cache) {
              assistantMsg.from_cache = true
            }
          } else if (event.type === 'sources') {
            assistantMsg.source_chunks = event.sources
          } else if (event.type === 'delta') {
            // 流式追加内容
            assistantMsg.content = (assistantMsg.content || '') + event.content
          } else if (event.type === 'done') {
            assistantMsg.grounded = event.grounded
            assistantMsg.unsupported_reason = event.unsupported_reason
            assistantMsg.supplement_note = event.supplement_note
            assistantMsg.verifier_result = event.verifier_result
            if (event.from_cache) {
              assistantMsg.from_cache = true
            }
          } else if (event.type === 'error') {
            assistantMsg.content = '抱歉，回答生成失败：' + event.message
          }
        }
      )
    } catch (error: any) {
      assistantMsg.content = '抱歉，回答生成失败，请重试。' + (error?.message || '')
    } finally {
      sending.value = false
    }
  }

  async function loadSessionHistory(sessionId: string) {
    const session = sessions.value.find(s => s.id === sessionId)
    if (!session) return

    session.loading = true
    try {
      const resp = await chatApi.getSessionHistory(sessionId)
      const data = resp.data.data
      session.messages = data.messages
      if (data.messages.length > 0 && session.title === '新对话') {
        const firstUser = data.messages.find(m => m.role === 'user')
        if (firstUser) {
          session.title = firstUser.content.slice(0, 20) + (firstUser.content.length > 20 ? '...' : '')
        }
      }
    } finally {
      session.loading = false
    }
  }

  /**
   * 从后端加载所有会话列表（不含消息），合并到本地 sessions。
   * 已存在的本地会话（含内存中的临时会话）不会被覆盖；
   * 后端新增的会话会被插入到列表最前。
   */
  async function loadSessions() {
    try {
      const resp = await chatApi.listSessions()
      const data = resp.data.data
      const remoteIds = new Set<string>()
      const newSessions: Session[] = []
      for (const item of data.items) {
        remoteIds.add(item.id)
        // 跳过本地已存在的（避免覆盖内存中的消息/loading 状态）
        const existing = sessions.value.find(s => s.id === item.id)
        if (existing) {
          // 仅更新标题等元信息
          if (item.title) existing.title = item.title
          continue
        }
        newSessions.push({
          id: item.id,
          title: item.title || '未命名会话',
          messages: [],
          loading: false
        })
      }
      // 合并：保留本地临时会话（temp- 开头），加上后端会话
      // 本地已存在的真实会话保留原位，新增的后端会话追加在前
      if (newSessions.length > 0) {
        sessions.value.push(...newSessions)
      }
    } catch (e) {
      // 静默失败，不影响主流程
      console.warn('加载会话列表失败', e)
    }
  }

  /**
   * 删除会话。
   * - 真实会话（非 temp-）调用后端删除接口
   * - 临时会话仅从内存移除
   * - 删除当前会话时自动切换到第一个可用会话，若无则新建
   */
  async function deleteSession(sessionId: string): Promise<boolean> {
    // 真实会话：调后端
    if (!sessionId.startsWith('temp-')) {
      try {
        await chatApi.deleteSession(sessionId)
      } catch (e) {
        console.error('删除会话失败', e)
        return false
      }
    }
    // 从内存移除
    const idx = sessions.value.findIndex(s => s.id === sessionId)
    if (idx >= 0) {
      sessions.value.splice(idx, 1)
    }
    // 切换当前会话
    if (currentSessionId.value === sessionId) {
      if (sessions.value.length > 0) {
        const next = sessions.value[0]
        currentSessionId.value = next.id
        // 真实会话且无消息时加载历史
        if (!next.id.startsWith('temp-') && next.messages.length === 0) {
          loadSessionHistory(next.id)
        }
      } else {
        // 没有会话了，新建一个
        createNewSession()
      }
    }
    return true
  }

  /**
   * 重命名会话。
   * - 真实会话（非 temp-）调用后端 PATCH 接口
   * - 临时会话仅更新内存标题
   */
  async function renameSession(sessionId: string, title: string): Promise<boolean> {
    const session = sessions.value.find(s => s.id === sessionId)
    if (!session) return false

    const oldTitle = session.title
    // 乐观更新：先改本地，失败回滚
    session.title = title

    if (!sessionId.startsWith('temp-')) {
      try {
        await chatApi.renameSession(sessionId, title)
      } catch (e) {
        console.error('重命名会话失败', e)
        session.title = oldTitle  // 回滚
        return false
      }
    }
    return true
  }

  function toggleDocumentFilter(docId: string) {
    const idx = selectedDocumentIds.value.indexOf(docId)
    if (idx >= 0) {
      selectedDocumentIds.value.splice(idx, 1)
    } else {
      selectedDocumentIds.value.push(docId)
    }
  }

  function clearDocumentFilter() {
    selectedDocumentIds.value = []
  }

  return {
    sessions,
    currentSessionId,
    sending,
    selectedDocumentIds,
    chatMode,
    getCurrentSession,
    createNewSession,
    switchSession,
    setChatMode,
    sendMessage,
    loadSessionHistory,
    loadSessions,
    deleteSession,
    renameSession,
    toggleDocumentFilter,
    clearDocumentFilter
  }
})
