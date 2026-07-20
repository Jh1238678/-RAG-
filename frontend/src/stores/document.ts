import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Document as DocItem, DocumentList } from '@/types'
import * as docApi from '@/api/document'

export const useDocumentStore = defineStore('document', () => {
  const documents = ref<DocItem[]>([])
  const total = ref(0)
  const loading = ref(false)

  async function fetchDocuments(params?: { status?: string; page?: number; page_size?: number }) {
    loading.value = true
    try {
      const resp = await docApi.getDocuments(params)
      const data = resp.data.data as DocumentList
      documents.value = data.items
      total.value = data.total
    } finally {
      loading.value = false
    }
  }

  async function uploadDocument(file: File) {
    const resp = await docApi.uploadDocument(file)
    await fetchDocuments()
    return resp.data.data
  }

  async function deleteDocument(id: string) {
    await docApi.deleteDocument(id)
    await fetchDocuments()
  }

  async function generateSummary(id: string) {
    const resp = await docApi.generateSummary(id)
    // 更新本地文档摘要
    const doc = documents.value.find(d => d.id === id)
    if (doc) {
      doc.summary = resp.data.data.summary
    }
    return resp.data.data
  }

  return {
    documents,
    total,
    loading,
    fetchDocuments,
    uploadDocument,
    deleteDocument,
    generateSummary
  }
})
