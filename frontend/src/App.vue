<template>
  <el-container class="app-container">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="app-aside">
      <div class="logo">
        <div class="logo-icon">
          <el-icon size="22"><ChatLineSquare /></el-icon>
        </div>
        <span v-show="!isCollapse" class="logo-text">AI 文档问答</span>
      </div>
      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapse"
        :router="true"
        background-color="transparent"
        text-color="#A5B4FC"
        active-text-color="#FFFFFF"
        class="app-menu"
      >
        <el-menu-item index="/chat">
          <el-icon><ChatDotRound /></el-icon>
          <template #title>智能问答</template>
        </el-menu-item>
        <el-menu-item index="/documents">
          <el-icon><Document /></el-icon>
          <template #title>文档管理</template>
        </el-menu-item>
        <el-menu-item index="/about">
          <el-icon><InfoFilled /></el-icon>
          <template #title>关于系统</template>
        </el-menu-item>
      </el-menu>
      <div class="collapse-btn" @click="isCollapse = !isCollapse">
        <el-icon><Fold v-if="!isCollapse" /><Expand v-else /></el-icon>
      </div>
    </el-aside>

    <!-- 主内容区 -->
    <el-container>
      <el-header class="app-header">
        <div class="header-title">
          {{ currentTitle }}
        </div>
        <div class="header-right">
          <el-tag :type="healthTagType" size="small" effect="plain" round>
            <el-icon><CircleCheck v-if="healthOk" /><Loading v-else /></el-icon>
            {{ healthOk ? '服务正常' : '检查中...' }}
          </el-tag>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { checkHealth } from '@/api/document'

const route = useRoute()
const isCollapse = ref(false)
const healthOk = ref(false)
let healthTimer: number | null = null

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => (route.meta.title as string) || '')
const healthTagType = computed(() => (healthOk.value ? 'success' : 'info'))

async function checkHealthStatus() {
  try {
    const resp = await checkHealth()
    healthOk.value = resp.data.data.status === 'ok'
  } catch {
    healthOk.value = false
  }
}

onMounted(() => {
  checkHealthStatus()
  healthTimer = window.setInterval(checkHealthStatus, 30000)
})
</script>

<style scoped>
/* Indigo SaaS 设计系统变量 */
.app-container {
  --indigo-500: #6366F1;
  --indigo-600: #4F46E5;
  --indigo-700: #4338CA;
  --indigo-900: #312E81;
  --indigo-950: #1E1B4B;
  --slate-50: #F8FAFC;
  --slate-100: #F1F5F9;
  --slate-200: #E2E8F0;
  --slate-400: #94A3B8;
  --slate-500: #64748B;
  --slate-600: #475569;
  --slate-700: #334155;
  --slate-800: #1E293B;
  --slate-900: #0F172A;
  --bg-page: #F5F3FF;
  --radius-md: 10px;
  --radius-lg: 14px;

  height: 100%;
}

.app-aside {
  background: linear-gradient(180deg, var(--indigo-950) 0%, var(--indigo-900) 100%);
  transition: width 0.3s ease;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 2px 0 12px rgba(30, 27, 75, 0.15);
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  gap: 10px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.logo-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--indigo-500);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #FFF;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
}

.logo-text {
  color: #FFF;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
  letter-spacing: 0.3px;
}

.app-menu {
  border-right: none;
  flex: 1;
  padding: 12px 10px;
}

.app-menu :deep(.el-menu-item) {
  border-radius: var(--radius-md);
  margin-bottom: 4px;
  height: 44px;
  line-height: 44px;
  transition: all 0.2s;
}

.app-menu :deep(.el-menu-item:hover) {
  background: rgba(99, 102, 241, 0.15) !important;
  color: #E0E7FF !important;
}

.app-menu :deep(.el-menu-item.is-active) {
  background: var(--indigo-500) !important;
  color: #FFFFFF !important;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.35);
}

.collapse-btn {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(165, 180, 252, 0.6);
  cursor: pointer;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  transition: all 0.2s;
}

.collapse-btn:hover {
  color: #FFFFFF;
  background: rgba(99, 102, 241, 0.15);
}

.app-header {
  background: #FFFFFF;
  border-bottom: 1px solid var(--slate-200);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  height: 56px;
  box-shadow: 0 1px 3px rgba(30, 27, 75, 0.04);
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--slate-800);
  letter-spacing: 0.2px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-main {
  padding: 0;
  background: var(--bg-page);
  overflow: hidden;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
