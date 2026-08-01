<template>
  <div id="app">
    <!-- 主界面 -->
    <template v-if="store.currentProjectPath && projectLoaded">
      <AppHeader />
      <div class="main-content">
        <PanelContainer />
      </div>
      <AppFooter />
    </template>

    <!-- 欢迎界面（无项目或加载失败） -->
    <div v-else class="welcome">
      <div class="welcome-content">
        <h1>⚡ 节点自动化</h1>
        <p>请打开一个项目文件夹</p>

        <!-- 缓存路径提示 -->
        <div v-if="cachedPath" class="cached-hint">
          <el-icon><InfoFilled /></el-icon>
          <span>上次打开：{{ cachedPath }}</span>
        </div>

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
import { ref, onMounted, computed } from 'vue'
import { useMainStore } from '@/stores'
import { ElMessage } from 'element-plus'
import { InfoFilled } from '@element-plus/icons-vue'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import PanelContainer from './components/PanelContainer.vue'

export default {
  components: { AppHeader, AppFooter, PanelContainer, InfoFilled },
  setup() {
    const store = useMainStore()
    const projectPathInput = ref('')
    const projectLoaded = ref(false)

    const cachedPath = computed(() => store.currentProjectPath || '')

    const loadProject = async (path) => {
      if (!path) return false
      try {
        await store.loadProjectByPath(path)
        projectLoaded.value = true
        return true
      } catch (err) {
        ElMessage.error('打开项目失败: ' + err.message)
        projectLoaded.value = false
        return false
      }
    }

    const handleOpenProject = async () => {
      const path = projectPathInput.value.trim()
      if (!path) {
        ElMessage.warning('请输入项目路径')
        return
      }
      const ok = await loadProject(path)
      if (ok) {
        projectPathInput.value = ''
        ElMessage.success(`已打开项目: ${store.currentProjectName}`)
      }
    }

    const handleOpenRecent = async (path) => {
      const ok = await loadProject(path)
      if (ok) {
        ElMessage.success(`已打开项目: ${store.currentProjectName}`)
      } else {
        // 从最近列表中移除无效路径
        store.recentProjects = store.recentProjects.filter(p => p.path !== path)
        localStorage.setItem('recentProjects', JSON.stringify(store.recentProjects))
      }
    }

    onMounted(async () => {
      await store.loadParams()

      // 如果有缓存的路径，填入输入框
      if (store.currentProjectPath) {
        projectPathInput.value = store.currentProjectPath
        // 尝试自动加载
        try {
          await store.loadProjectData()
          await store.loadContext()
          projectLoaded.value = true
          ElMessage.success(`已自动加载项目: ${store.currentProjectName}`)
        } catch (err) {
          // 自动加载失败，回到欢迎界面，但保留路径在输入框中
          ElMessage.warning('自动加载项目失败，请检查路径后重新打开')
          store.currentProjectPath = null
          projectLoaded.value = false
          // 不删除 localStorage，路径还保留着，用户可以看到
        }
      }
    })

    return {
      store,
      projectPathInput,
      cachedPath,
      projectLoaded,
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
.cached-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #8a8fa8;
  font-size: 14px;
  margin-bottom: 12px;
}
.cached-hint .el-icon {
  color: #409EFF;
}
.recent {
  margin-top: 30px;
  font-size: 14px;
  color: #8a8fa8;
}
.recent .el-link {
  color: #409EFF;
}
/* ⭐ 全局弹窗层级梯队管控 */
/* 第 3 层级：警告/重名提示 MessageBox 最高 (z-index: 1100) */
.high-zindex-messagebox,
.el-message-box__wrapper {
    z-index: 1100 !important;
}

/* 关联的 Element 蒙层同步压在 1099 */
.v-modal {
    z-index: 1099 !important;
}
</style>