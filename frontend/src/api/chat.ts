import request from './request'
import type {
  ApiResponse,
  ChatRequest,
  ChatResponse,
  ChatStreamEvent,
  SessionCreateResponse,
  SessionHistory,
  SessionList
} from '@/types'

// 新建会话
export function createSession(data: { title?: string; document_ids?: string[] }) {
  return request.post<ApiResponse<SessionCreateResponse>>('/api/chat/session', data)
}

// 列出所有会话
export function listSessions(limit = 100) {
  return request.get<ApiResponse<SessionList>>('/api/chat/sessions', {
    params: { limit }
  })
}

// 删除会话
export function deleteSession(sessionId: string) {
  return request.delete<ApiResponse<{ deleted: boolean }>>(`/api/chat/session/${sessionId}`)
}

// 重命名会话
export function renameSession(sessionId: string, title: string) {
  return request.patch<ApiResponse<any>>(`/api/chat/session/${sessionId}/title`, { title })
}

// 问答（非流式，保留作为 fallback）
export function chat(data: ChatRequest) {
  return request.post<ApiResponse<ChatResponse>>('/api/chat', data, {
    timeout: 180000
  })
}

// 问答（SSE 流式）。通过 fetch + ReadableStream 解析 text/event-stream
export async function chatStream(
  data: ChatRequest,
  onEvent: (event: ChatStreamEvent) => void,
  onError?: (err: Error) => void
) {
  const resp = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data)
  })

  if (!resp.ok) {
    const errText = await resp.text().catch(() => '')
    throw new Error(`HTTP ${resp.status}: ${errText}`)
  }
  if (!resp.body) {
    throw new Error('Response body is null')
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      // SSE 事件以 "\n\n" 分隔
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const part of parts) {
        const lines = part.split('\n')
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6)
            try {
              const event = JSON.parse(jsonStr) as ChatStreamEvent
              onEvent(event)
            } catch (e) {
              console.warn('Failed to parse SSE event:', jsonStr, e)
            }
          }
        }
      }
    }
    // 处理 buffer 中剩余数据
    if (buffer.trim().startsWith('data: ')) {
      try {
        const jsonStr = buffer.trim().slice(6)
        const event = JSON.parse(jsonStr) as ChatStreamEvent
        onEvent(event)
      } catch (e) {
        // 忽略不完整数据
      }
    }
  } catch (err: any) {
    if (onError) {
      onError(err)
    } else {
      throw err
    }
  }
}

// 会话历史
export function getSessionHistory(sessionId: string, limit = 50) {
  return request.get<ApiResponse<SessionHistory>>(`/api/chat/session/${sessionId}`, {
    params: { limit }
  })
}
