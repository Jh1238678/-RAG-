import request from './request'
import type {
  ApiResponse,
  DocumentList,
  DocumentDetail,
  UploadResponse,
  SummaryResponse,
  DeleteResponse,
  HealthStatus
} from '@/types'

// 健康检查
export function checkHealth() {
  return request.get<ApiResponse<HealthStatus>>('/health')
}

// 上传文档
export function uploadDocument(file: File) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post<ApiResponse<UploadResponse>>('/api/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000 // 上传大文件 5 分钟
  })
}

// 文档列表
export function getDocuments(params?: { status?: string; page?: number; page_size?: number }) {
  return request.get<ApiResponse<DocumentList>>('/api/documents', { params })
}

// 文档详情
export function getDocumentDetail(id: string) {
  return request.get<ApiResponse<DocumentDetail>>(`/api/documents/${id}`)
}

// 删除文档
export function deleteDocument(id: string) {
  return request.delete<ApiResponse<DeleteResponse>>(`/api/documents/${id}`)
}

// 生成摘要
export function generateSummary(id: string) {
  return request.post<ApiResponse<SummaryResponse>>(`/api/summary/${id}`, {}, {
    timeout: 180000
  })
}
