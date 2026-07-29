<template>
  <header class="app-header">
    <div class="left-group">
      <el-icon class="menu-icon" @click="toggleMenu"><Menu /></el-icon>
      <span class="logo">⚡ 节点自动化</span>
    </div>

    <div class="project-selector">
      <el-button size="small" type="primary" @click="setWorkspace">
        {{ workspaceStatus }}
      </el-button>
      <el-select
        v-model="store.currentProject"
        placeholder="选择项目"
        size="small"
        @change="onProjectChange"
        style="width: 150px; margin-left: 8px;"
        :disabled="!store.workspaceHandle"
      >
        <el-option
          v-for="p in store.projects"
          :key="p"
          :label="p"
          :value="p"
        />
      </el-select>
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
import { ElMessage } from 'element-plus'
import ScreenshotTool from './ScreenshotTool.vue'
import axios from 'axios'

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
  computed: {
    workspaceStatus() {
      return this.store.workspaceHandle ? '📁 工作区已设置' : '📂 设置工作区'
    }
  },
  methods: {
    async setWorkspace() {
      await this.store.setWorkspaceRoot()
      if (this.store.workspaceHandle && this.store.currentProject) {
        await this.store.loadProjectData()
      }
    },
    async onProjectChange(project) {
      if (!project) return
      this.store.currentProject = project
      await this.store.loadProjectData()
    },
    onMenuSelect(index) {
      this.activeMenu = index
      if (index === 'screenshot') {
        this.openScreenshot()
      }
    },
    openScreenshot() {
      this.$refs.screenshotTool.open()
    },
    async runTask() {
  if (!this.store.currentTaskId) {
    ElMessage.warning('请先选择一个任务')
    return
  }
  const project = this.store.currentProject
  const taskId = this.store.currentTaskId
  try {
    ElMessage.info('任务执行中...')
    const res = await axios.post(`/api/projects/${project}/run`, {
      task_id: taskId,
      start_node_id: null
    })
    if (res.data.status === 'success') {
      ElMessage.success('任务执行完成')
    } else {
      ElMessage.error('执行失败: ' + (res.data.message || '未知错误'))
    }
  } catch (err) {
    console.error('执行错误', err)
    ElMessage.error('执行请求失败: ' + (err.response?.data?.detail || err.message))
  }
},
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
  flex-shrink: 0;
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