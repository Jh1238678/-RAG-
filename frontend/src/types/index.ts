// 类型定义：与后端 schemas.py 对齐

export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

export interface Document {
  id: string
  file_name: string
  file_type: string
  file_size?: number | null
  status: 'pending' | 'parsing' | 'indexed' | 'failed'
  chunk_count: number
  summary?: string | null
  error_msg?: string | null
  created_at: string
  updated_at?: string | null
}

export interface DocumentList {
  total: number
  items: Document[]
}

export interface ChunkPreview {
  id: string
  chunk_index: number
  content: string
  page_num?: number | null
  char_count?: number | null
}

export interface DocumentDetail extends Document {
  chunks_preview: ChunkPreview[]
}

export interface UploadResponse {
  document_id: string
  file_name: string
  status: string
  chunk_count: number
}

export interface DeleteResponse {
  deleted: boolean
}

export interface SummaryResponse {
  document_id: string
  summary: string
  segment_count: number
}

export interface SourceChunk {
  chunk_id: string
  document_id: string
  document_name: string
  page_num?: number | null
  snippet: string
  score: number
}

export interface ChatRequest {
  question: string
  session_id?: string
  document_ids?: string[]
  /** 问答模式：strict（严格依据文档，不可外推） | open（允许适度解释） */
  mode?: 'strict' | 'open'
}

export type ChatMode = 'strict' | 'open'

export type VerifierVerdict = 'supported' | 'partial' | 'unsupported'

export interface VerifierResult {
  verdict: VerifierVerdict
  reason?: string | null
  unsupported_spans: string[]
}

/** SSE 流式事件 */
export type ChatStreamEvent =
  | { type: 'meta'; session_id: string; mode: ChatMode; rewritten_query?: string | null; from_cache: boolean }
  | { type: 'sources'; sources: SourceChunk[] }
  | { type: 'delta'; content: string }
  | {
      type: 'done'
      grounded?: boolean | null
      unsupported_reason?: string | null
      supplement_note?: string | null
      verifier_result?: VerifierResult | null
      from_cache: boolean
    }
  | { type: 'error'; message: string }

export interface ChatResponse {
  session_id: string
  answer: string
  rewritten_query?: string | null
  sources: SourceChunk[]
  /** 本次问答使用的模式 */
  mode: ChatMode
  /** 严格模式：答案是否被证据充分支持 */
  grounded?: boolean | null
  /** 严格模式：未命中拒答原因 */
  unsupported_reason?: string | null
  /** 开放模式：补充说明标识 */
  supplement_note?: string | null
  /** 严格模式可选：答案校验结果 */
  verifier_result?: VerifierResult | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  source_chunks?: SourceChunk[] | null
  rewritten_query?: string | null
  created_at: string
}

export interface SessionHistory {
  session_id: string
  messages: Message[]
}

export interface SessionCreateResponse {
  session_id: string
}

export interface SessionItem {
  id: string
  title: string | null
  document_ids: string[] | null
  message_count: number
  created_at: string
  updated_at: string | null
}

export interface SessionList {
  total: number
  items: SessionItem[]
}

export interface HealthStatus {
  status: string
  version: string
  db: string
  faiss_loaded: boolean
}
