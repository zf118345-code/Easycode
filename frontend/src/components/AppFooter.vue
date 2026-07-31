<template>
  <footer class="app-footer">
    <div class="footer-left">
      <span>就绪 | 项目: {{ currentProject }}</span>
    </div>
    <div class="footer-center">
      <span class="panel-status" @click="showPanelDialog">
        <el-icon><Monitor /></el-icon>
        {{ panelStatus }}
      </span>
    </div>
    <div class="footer-right">
      <span>⚡ 执行状态: 空闲</span>
    </div>

    <PanelSettingsDialog
      v-model:visible="dialogVisible"
      @apply="handleApplyContext"
    />
  </footer>
</template>

<script>
import { useMainStore } from '@/stores'
import { ElMessage } from 'element-plus'  // ← 添加这行
import { Monitor } from '@element-plus/icons-vue'
import PanelSettingsDialog from './PanelSettingsDialog.vue'

export default {
  components: { Monitor, PanelSettingsDialog },
  data() {
    return { dialogVisible: false }
  },
  setup() {
    const store = useMainStore()
    return { store }
  },
  computed: {
    currentProject() {
      return this.store.currentProject || '未选择'
    },
    panelStatus() {
      const ctx = this.store.currentContext
      if (ctx && ctx.windowTitle) {
        const label = ctx.isEmulator ? '📱' : '🪟'
        return `${label} 工作面板：${ctx.windowTitle}`
      }
      return '🖥️ 工作面板：Windows 桌面'
    }
  },
  methods: {
    showPanelDialog() {
      this.dialogVisible = true
    },
    async handleApplyContext(context) {
      try {
        await this.store.setCurrentContext(context)
        ElMessage.success('工作面板已更新并保存')
      } catch (err) {
        ElMessage.error('保存失败: ' + err.message)
      }
    }
  }
}
</script>

<style scoped>
.app-footer {
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #2d2d44;
  border-top: 1px solid #3d3d5a;
  color: #8a8fa8;
  font-size: 12px;
  flex-shrink: 0;
}
.footer-left, .footer-center, .footer-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.panel-status {
  cursor: pointer;
  padding: 2px 10px;
  border-radius: 12px;
  background: #3d3d5a;
  transition: background 0.2s;
}
.panel-status:hover {
  background: #4d4d6a;
}
.panel-status .el-icon {
  margin-right: 4px;
}
</style>