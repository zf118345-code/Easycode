<template>
  <div id="app">
    <AppHeader />
    <div class="main-content">
      <PanelContainer />
    </div>
    <AppFooter />
  </div>
</template>

<script>
import { onMounted } from 'vue'
import { useMainStore } from '@/stores'
import { ElMessageBox, ElMessage } from 'element-plus'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'
import PanelContainer from './components/PanelContainer.vue'

export default {
  components: { AppHeader, AppFooter, PanelContainer },
  setup() {
    const store = useMainStore()

    onMounted(async () => {
      await store.loadParams()

      // 恢复记忆
      const lastWorkspace = localStorage.getItem('lastWorkspace')
      const lastProject = localStorage.getItem('lastProject')
      if (lastWorkspace && lastProject) {
        try {
          await ElMessageBox.confirm(
            `是否恢复上次的项目：${lastWorkspace}/${lastProject}？`,
            '恢复项目',
            { confirmButtonText: '恢复', cancelButtonText: '重新选择', type: 'info' }
          )
          store.currentProject = lastProject
          ElMessage.info('请点击顶部“设置工作区”按钮选择工作区目录')
        } catch {
          // 用户取消
        }
      }
    })

    return { store }
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
</style>