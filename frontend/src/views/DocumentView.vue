<template>
  <div class="document-view">
    <!-- 操作栏 -->
    <div class="toolbar">
      <el-upload
        ref="uploadRef"
        :show-file-list="false"
        :before-upload="beforeUpload"
        :http-request="handleUpload"
        accept=".pdf,.docx,.md,.txt"
        :multiple="false"
      >
        <el-button type="primary" :icon="Upload" :loading="uploading">
          上传文档
        </el-button>
      </el-upload>
      <el-button :icon="Refresh" @click="refresh" :loading="store.loading">刷新</el-button>
      <el-select
        v-model="filterStatus"
        placeholder="状态筛选"
        clearable
        style="width: 140px"
        @change="refresh"
      >
        <el-option label="全部" value="" />
        <el-option label="已索引" value="indexed" />
        <el-option label="处理中" value="parsing" />
        <el-option label="失败" value="failed" />
      </el-select>
      <div class="toolbar-info">
        共 {{ store.total }} 篇文档
      </div>
    </div>

    <!-- 文档列表 -->
    <el-table
      :data="store.documents"
      v-loading="store.loading"
      stripe
      style="width: 100%"
      :max-height="tableHeight"
    >
      <el-table-column label="文件名" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          <el-icon class="file-icon"><component :is="getFileIcon(row.file_type)" /></el-icon>
          {{ row.file_name }}
        </template>
      </el-table-column>
      <el-table-column label="类型" width="80" align="center">
        <template #default="{ row }">
          <el-tag size="small" :type="getFileTagType(row.file_type)">{{ row.file_type.toUpperCase() }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="大小" width="100" align="right">
        <template #default="{ row }">
          {{ formatSize(row.file_size) }}
        </template>
      </el-table-column>
      <el-table-column label="分块数" width="90" align="center">
        <template #default="{ row }">
          {{ row.chunk_count }}
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="getStatusType(row.status)" size="small">
            {{ getStatusText(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="上传时间" width="170">
        <template #default="{ row }">
          {{ formatTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="showDetail(row)">详情</el-button>
          <el-button size="small" type="warning" @click="showSummary(row)" :disabled="row.status !== 'indexed'">摘要</el-button>
          <el-button size="small" type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
      <template #empty>
        <el-empty description="暂无文档，点击上方上传按钮添加" />
      </template>
    </el-table>

    <!-- 详情对话框 -->
    <el-dialog v-model="detailVisible" title="文档详情" width="700px" top="5vh">
      <template v-if="detailData">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="文件名">{{ detailData.file_name }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ detailData.file_type.toUpperCase() }}</el-descriptions-item>
          <el-descriptions-item label="大小">{{ formatSize(detailData.file_size) }}</el-descriptions-item>
          <el-descriptions-item label="分块数">{{ detailData.chunk_count }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(detailData.status)" size="small">{{ getStatusText(detailData.status) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="上传时间">{{ formatTime(detailData.created_at) }}</el-descriptions-item>
          <el-descriptions-item v-if="detailData.error_msg" label="错误信息" :span="2">
            <span style="color: #f56c6c">{{ detailData.error_msg }}</span>
          </el-descriptions-item>
        </el-descriptions>

        <div v-if="detailData.summary" style="margin-top: 16px">
          <h4 style="margin-bottom: 8px">文档摘要</h4>
          <div class="summary-box">{{ detailData.summary }}</div>
        </div>

        <div v-if="detailData.chunks_preview && detailData.chunks_preview.length" style="margin-top: 16px">
          <h4 style="margin-bottom: 8px">内容预览（前 5 块）</h4>
          <div v-for="chunk in detailData.chunks_preview.slice(0, 5)" :key="chunk.id" class="chunk-preview">
            <div class="chunk-meta">
              <el-tag size="small" type="info">块 {{ chunk.chunk_index }}</el-tag>
              <el-tag v-if="chunk.page_num" size="small">第 {{ chunk.page_num }} 页</el-tag>
              <span class="char-count">{{ chunk.char_count }} 字</span>
            </div>
            <div class="chunk-content">{{ chunk.content }}</div>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- 摘要对话框 -->
    <el-dialog v-model="summaryVisible" title="文档摘要" width="600px">
      <div v-loading="summaryLoading">
        <div v-if="summaryText" class="summary-box large">{{ summaryText }}</div>
        <el-empty v-else description="点击下方按钮生成摘要" />
      </div>
      <template #footer>
        <el-button @click="summaryVisible = false">关闭</el-button>
        <el-button type="primary" @click="doGenerateSummary" :loading="summaryLoading" :disabled="!currentSummaryDoc">
          {{ summaryText ? '重新生成' : '生成摘要' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { Upload, Refresh, Document, Picture, Tickets, Files } from '@element-plus/icons-vue'
import { useDocumentStore } from '@/stores/document'
import * as docApi from '@/api/document'
import type { Document as DocItem, DocumentDetail } from '@/types'

const store = useDocumentStore()

const uploading = ref(false)
const filterStatus = ref('')
const tableHeight = computed(() => 'calc(100vh - 180px)')

// 详情
const detailVisible = ref(false)
const detailData = ref<DocumentDetail | null>(null)

// 摘要
const summaryVisible = ref(false)
const summaryLoading = ref(false)
const summaryText = ref('')
const currentSummaryDoc = ref<DocItem | null>(null)

onMounted(() => {
  refresh()
})

async function refresh() {
  await store.fetchDocuments({
    status: filterStatus.value || undefined,
    page: 1,
    page_size: 100
  })
}

function beforeUpload(file: File): boolean {
  const allowed = ['.pdf', '.docx', '.md', '.txt']
  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!allowed.includes(ext)) {
    ElMessage.error('仅支持 PDF、DOCX、MD、TXT 格式')
    return false
  }
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.error('文件大小不能超过 50MB')
    return false
  }
  return true
}

async function handleUpload(options: any) {
  uploading.value = true
  try {
    const result = await store.uploadDocument(options.file)
    ElMessage.success(`上传成功：${result.file_name}，已切分 ${result.chunk_count} 块`)
  } catch (error) {
    // 错误已在拦截器处理
  } finally {
    uploading.value = false
  }
}

async function showDetail(doc: DocItem) {
  try {
    const resp = await docApi.getDocumentDetail(doc.id)
    detailData.value = resp.data.data
    detailVisible.value = true
  } catch (error) {
    // 错误已处理
  }
}

function showSummary(doc: DocItem) {
  currentSummaryDoc.value = doc
  summaryText.value = doc.summary || ''
  summaryVisible.value = true
}

async function doGenerateSummary() {
  if (!currentSummaryDoc.value) return
  summaryLoading.value = true
  try {
    const result = await store.generateSummary(currentSummaryDoc.value.id)
    summaryText.value = result.summary
    ElMessage.success('摘要生成成功')
  } catch (error) {
    // 错误已处理
  } finally {
    summaryLoading.value = false
  }
}

async function handleDelete(doc: DocItem) {
  try {
    await ElMessageBox.confirm(
      `确认删除文档 "${doc.file_name}"？该操作将同时删除所有分块和索引数据，不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await store.deleteDocument(doc.id)
    ElMessage.success('删除成功')
  } catch (error) {
    // 取消或错误
  }
}

// 工具函数
function formatSize(bytes?: number | null): string {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

function formatTime(time: string): string {
  return new Date(time).toLocaleString('zh-CN')
}

function getFileIcon(type: string) {
  const map: Record<string, any> = { pdf: Files, docx: Document, md: Tickets, txt: Tickets }
  return map[type] || Document
}

function getFileTagType(type: string) {
  const map: Record<string, string> = { pdf: 'danger', docx: 'primary', md: 'success', txt: 'info' }
  return map[type] || 'info'
}

function getStatusType(status: string) {
  const map: Record<string, string> = {
    pending: 'info',
    parsing: 'warning',
    indexed: 'success',
    failed: 'danger'
  }
  return map[status] || 'info'
}

function getStatusText(status: string) {
  const map: Record<string, string> = {
    pending: '待处理',
    parsing: '处理中',
    indexed: '已索引',
    failed: '失败'
  }
  return map[status] || status
}
</script>

<style scoped>
/* Indigo SaaS 设计系统变量 */
.document-view {
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
  --emerald-500: #10B981;
  --emerald-600: #059669;
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
  --bg-page: #F5F3FF;
  --bg-card: #FFFFFF;
  --border-color: #E2E8F0;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;

  padding: 24px;
  height: 100%;
  overflow: auto;
  background: var(--bg-card);
  margin: 16px;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-color);
  box-shadow: 0 1px 3px rgba(99, 102, 241, 0.06);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

/* 美化 Element Plus 按钮为 Indigo 主题 */
.toolbar :deep(.el-button--primary) {
  background: var(--indigo-500);
  border-color: var(--indigo-500);
  border-radius: var(--radius-md);
  font-weight: 500;
  transition: all 0.2s;
}

.toolbar :deep(.el-button--primary:hover) {
  background: var(--indigo-400);
  border-color: var(--indigo-400);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}

.toolbar :deep(.el-button--default) {
  border-radius: var(--radius-md);
  color: var(--slate-600);
  border-color: var(--border-color);
}

.toolbar :deep(.el-button--default:hover) {
  color: var(--indigo-500);
  border-color: var(--indigo-400);
  background: var(--indigo-50);
}

.toolbar :deep(.el-select .el-input__wrapper) {
  border-radius: var(--radius-md);
}

.toolbar-info {
  margin-left: auto;
  color: var(--slate-500);
  font-size: 13px;
  font-weight: 500;
}

/* 文件图标 */
.file-icon {
  vertical-align: middle;
  margin-right: 6px;
  color: var(--indigo-500);
  font-size: 16px;
}

/* 表格美化 */
.document-view :deep(.el-table) {
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-color);
}

.document-view :deep(.el-table th) {
  background: var(--indigo-50) !important;
  color: var(--indigo-900) !important;
  font-weight: 600;
}

.document-view :deep(.el-table th .cell) {
  font-size: 13px;
}

.document-view :deep(.el-table tr:hover > td) {
  background: var(--indigo-50) !important;
}

.document-view :deep(.el-table--striped .el-table__body tr.el-table__row--striped td) {
  background: var(--slate-50);
}

/* 对话框美化 */
.document-view :deep(.el-dialog) {
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.document-view :deep(.el-dialog__header) {
  background: var(--indigo-50);
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.document-view :deep(.el-dialog__title) {
  color: var(--indigo-900);
  font-weight: 600;
}

.document-view :deep(.el-dialog__body) {
  padding: 20px;
}

/* 摘要框 */
.summary-box {
  background: var(--indigo-50);
  padding: 14px 16px;
  border-radius: var(--radius-md);
  line-height: 1.8;
  white-space: pre-wrap;
  color: var(--slate-700);
  border-left: 3px solid var(--indigo-400);
  font-size: 14px;
}

.summary-box.large {
  min-height: 200px;
}

/* chunk 预览 */
.chunk-preview {
  margin-bottom: 14px;
  border-left: 3px solid var(--indigo-400);
  padding-left: 14px;
}

.chunk-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.char-count {
  color: var(--slate-400);
  font-size: 12px;
}

.chunk-content {
  background: var(--slate-50);
  padding: 10px 14px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.7;
  color: var(--slate-700);
  max-height: 120px;
  overflow: auto;
  border: 1px solid var(--border-color);
}

/* Descriptions 美化 */
.document-view :deep(.el-descriptions__label) {
  color: var(--slate-500);
  font-weight: 500;
  background: var(--slate-50) !important;
}

.document-view :deep(.el-descriptions__content) {
  color: var(--slate-800);
}

/* 响应式 */
@media (max-width: 768px) {
  .document-view {
    margin: 8px;
    padding: 16px;
  }
}
</style>
