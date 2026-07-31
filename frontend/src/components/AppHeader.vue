<template>
  <header class="app-header">
    <div class="left-group">
      <el-icon class="menu-icon" @click="toggleMenu"><Menu /></el-icon>
      <span class="logo">⚡ 节点自动化</span>
    </div>

    <div class="project-selector">
      <span class="project-name">📁 {{ store.currentProjectName || '未选择项目' }}</span>
      <el-button size="small" type="primary" @click="switchProject">
        🔄 切换
      </el-button>
    </div>

    <el-menu
      mode="horizontal"
      :default-active="activeMenu"
      background-color="#2d2d44"
      text-color="#cfd3e6"
      active-text-color="#409EFF"
      @select="onMenuSelect"
      class="menu-bar"
    >
      <el-menu-item index="file">文件</el-menu-item>
      <el-menu-item index="edit">编辑</el-menu-item>
      <el-menu-item index="view">视图</el-menu-item>
      <el-menu-item index="screenshot" @click="openScreenshot">截图工具</el-menu-item>
      <el-menu-item index="run">运行</el-menu-item>
    </el-menu>

    <div class="header-actions">
      <el-button type="primary" size="small" @click="runTask">▶ 运行</el-button>
    </div>

    <ScreenshotTool ref="screenshotTool" />
  </header>
</template>

<script>
import { Menu } from '@element-plus/icons-vue'
import { useMainStore } from '@/stores'
import { ElMessage, ElMessageBox } from 'element-plus'
import ScreenshotTool from './ScreenshotTool.vue'

export default {
  components: { Menu, ScreenshotTool },
  data() {
    return {
      activeMenu: 'file'
    }
  },
  setup() {
    const store = useMainStore()
    return { store }
  },
  methods: {
    // ====== 切换项目 ======
    async switchProject() {
      try {
        const { value: path } = await ElMessageBox.prompt('请输入新的项目完整路径', '切换项目', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          inputValue: this.store.currentProjectPath || '',
          inputPattern: /^[a-zA-Z]:[\\/].+/,
          inputErrorMessage: '请输入有效的绝对路径（如 D:/MyProjects/demo）'
        })
        if (path) {
          await this.store.loadProjectByPath(path)
          ElMessage.success(`已切换到项目: ${this.store.currentProjectName}`)
          // 刷新节点列表
          this.store.selectedNodeId = null
        }
      } catch (err) {
        if (err !== 'cancel') {
          ElMessage.error('切换失败: ' + err.message)
        }
      }
    },

    // ====== 菜单选择 ======
    onMenuSelect(index) {
      this.activeMenu = index
      if (index === 'screenshot') this.openScreenshot()
    },

    // ====== 截图工具 ======
    openScreenshot() {
      this.$refs.screenshotTool.open()
    },

    // ====== 运行任务 ======
    async runTask() {
      if (!this.store.currentTaskId) {
        ElMessage.warning('请先选择一个任务')
        return
      }
      try {
        ElMessage.info('任务执行中...')
        const result = await this.store.runTask(this.store.currentTaskId, null)
        if (result.status === 'started') {
          ElMessage.success('任务已启动，请查看执行状态')
        } else {
          ElMessage.error('执行失败: ' + (result.message || '未知错误'))
        }
      } catch (err) {
        ElMessage.error('执行请求失败: ' + (err.response?.data?.detail || err.message))
        console.error(err)
      }
    },

    // ====== 菜单 ======
    toggleMenu() {
      // 预留
    }
  }
}
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 12px;
  background: #2d2d44;
  border-bottom: 1px solid #3d3d5a;
  flex-shrink: 0;
  gap: 12px;
}
.left-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.menu-icon {
  color: #cfd3e6;
  font-size: 20px;
  cursor: pointer;
}
.menu-icon:hover {
  color: #409EFF;
}
.logo {
  color: #cfd3e6;
  font-weight: bold;
  font-size: 16px;
}
.project-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.project-name {
  color: #cfd3e6;
  font-weight: 500;
}
.menu-bar {
  flex: 1;
  border-bottom: none;
  background: transparent !important;
}
.menu-bar .el-menu-item {
  height: 40px;
  line-height: 40px;
}
.header-actions {
  display: flex;
  gap: 8px;
}
</style>