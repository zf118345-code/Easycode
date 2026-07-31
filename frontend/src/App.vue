<template>
  <div id="app">
    <!-- 主界面 -->
    <template v-if="store.currentProjectPath">
      <AppHeader />
      <div class="main-content">
        <PanelContainer />
      </div>
      <AppFooter />
    </template>

    <!-- 欢迎界面（无项目） -->
    <div v-else class="welcome">
      <div class="welcome-content">
        <h1>⚡ 节点自动化</h1>
        <p>请打开一个项目文件夹</p>
        <div class="open-section">
          <el-input
            v-model="projectPathInput"
            placeholder="输入项目完整路径，如 D:/MyProjects/demo"
            style="width: 500px;"
            clearable
            @keyup.enter="handleOpenProject"
          />
          <div style="margin-top: 12px;">
            <el-button type="primary" size="large" @click="handleOpenProject">
              📂 打开项目
            </el-button>
          </div>
        </div>
        <div v-if="store.recentProjects.length" class="recent">
          <span>最近打开：</span>
          <el-link
            v-for="p in store.recentProjects"
            :key="p.path"
            @click="handleOpenRecent(p.path)"
            style="margin:0 8px;"
          >
            {{ p.name }}
          </el-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useMainStore } from '@/stores'
import { ElMessage } from 'element-plus'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import PanelContainer from './components/PanelContainer.vue'

export default {
  components: { AppHeader, AppFooter, PanelContainer },
  setup() {
    const store = useMainStore()
    const projectPathInput = ref('')

    const handleOpenProject = async () => {
      const path = projectPathInput.value.trim()
      if (!path) {
        ElMessage.warning('请输入项目路径')
        return
      }
      try {
        await store.loadProjectByPath(path)
        projectPathInput.value = ''
        ElMessage.success(`已打开项目: ${store.currentProjectName}`)
      } catch (err) {
        ElMessage.error('打开项目失败: ' + err.message)
      }
    }

    const handleOpenRecent = async (path) => {
      try {
        await store.loadProjectByPath(path)
        ElMessage.success(`已打开项目: ${store.currentProjectName}`)
      } catch (err) {
        ElMessage.error('打开项目失败: ' + err.message)
        // 从最近列表中移除无效路径
        store.recentProjects = store.recentProjects.filter(p => p.path !== path)
        localStorage.setItem('recentProjects', JSON.stringify(store.recentProjects))
      }
    }

    onMounted(async () => {
      await store.loadParams()
      // 如果有保存的项目路径，自动加载
      if (store.currentProjectPath) {
        try {
          await store.loadProjectData()
          ElMessage.success(`已自动打开项目: ${store.currentProjectName}`)
        } catch (err) {
          ElMessage.error('自动加载项目失败，请重新打开')
          store.currentProjectPath = null
          localStorage.removeItem('currentProjectPath')
        }
      }
    })

    return {
      store,
      projectPathInput,
      handleOpenProject,
      handleOpenRecent
    }
  }
}
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}
html, body, #app {
  height: 100%;
  overflow: hidden;
  font-family: 'Microsoft YaHei', 'Segoe UI', sans-serif;
}
#app {
  display: flex;
  flex-direction: column;
  background: #1e1e2f;
}
.main-content {
  flex: 1;
  overflow: hidden;
  position: relative;
}

.welcome {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1e1e2f;
  color: #cfd3e6;
}
.welcome-content {
  text-align: center;
}
.welcome-content h1 {
  font-size: 48px;
  margin-bottom: 16px;
}
.welcome-content p {
  font-size: 18px;
  color: #8a8fa8;
  margin-bottom: 30px;
}
.open-section {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.recent {
  margin-top: 30px;
  font-size: 14px;
  color: #8a8fa8;
}
.recent .el-link {
  color: #409EFF;
}
</style>