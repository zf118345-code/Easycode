<!-- frontend/src/App.vue -->
<template>
    <div id="app" @contextmenu.prevent>
        <!-- 1. 客户 Player 专有轻量模式 -->
        <template v-if="isPlayerMode">
            <PlayerView />
        </template>

        <!-- 2. 开发者 Studio IDE 模式：加载项目并挂载 IDE 骨架 -->
        <template v-else-if="store.currentProjectPath && projectLoaded">
            <IdeLayout />
        </template>

        <!-- 3. 开发者 Studio IDE 欢迎界面（无项目或加载失败） -->
        <div v-else class="welcome">
            <div class="welcome-content">
                <h1>⚡ Easycode 自动化工作台</h1>
                <p>请选择并打开一个项目文件夹以开始编排</p>

                <div v-if="cachedPath" class="cached-hint">
                    <el-icon><InfoFilled /></el-icon>
                    <span>上次打开：{{ cachedPath }}</span>
                </div>

                <div class="open-section">
                    <el-input v-model="projectPathInput"
                              placeholder="输入项目绝对路径，如 D:/MyProjects/demo"
                              style="width: 500px;"
                              clearable
                              @keyup.enter="handleOpenProject" />
                    <div style="margin-top: 12px;">
                        <el-button type="primary" size="large" @click="handleOpenProject">
                            📂 打开项目
                        </el-button>
                    </div>
                </div>

                <div v-if="store.recentProjects?.length" class="recent">
                    <span>最近打开：</span>
                    <el-link v-for="p in (store.recentProjects || [])"
                             :key="p.path"
                             style="margin: 0 8px;"
                             @click="handleOpenRecent(p.path)">
                        {{ p.name }}
                    </el-link>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, onMounted, computed } from 'vue'
    import { useProjectStore } from '@/stores'
    import { ElMessage } from 'element-plus'
    import { InfoFilled } from '@element-plus/icons-vue'
    import IdeLayout from '@/layouts/IdeLayout.vue'
    import PlayerView from '@/views/PlayerView.vue'

    const store = useProjectStore()
    const projectPathInput = ref('')
    const projectLoaded = ref(false)

    // ⚡ 自动探测是否为 Player 运行模式（可以通过 URL 参数或 window 全局变量触发）
    const isPlayerMode = computed(() => {
        const urlParams = new URLSearchParams(window.location.search)
        return urlParams.get('mode') === 'player' || window.__EASYCODE_PLAYER_MODE__ === true
    })

    const cachedPath = computed(() => store.currentProjectPath || '')

    // 统一的项目加载入口函数
    const loadProject = async (path) => {
        if (!path) return false
        try {
            await store.loadProjectByPath(path)
            projectLoaded.value = true
            return true
        } catch (err) {
            ElMessage.error('打开项目失败: ' + (err.message || '路径无效或文件缺失'))
            projectLoaded.value = false
            return false
        }
    }

    // 手动输入路径并打开
    const handleOpenProject = async () => {
        const path = projectPathInput.value.trim()
        if (!path) {
            return ElMessage.warning('请输入项目路径')
        }
        const ok = await loadProject(path)
        if (ok) {
            projectPathInput.value = ''
            ElMessage.success(`已打开项目: ${store.currentProjectName}`)
        }
    }

    // 点击“最近打开”历史列表
    const handleOpenRecent = async (path) => {
        const ok = await loadProject(path)
        if (ok) {
            ElMessage.success(`已打开项目: ${store.currentProjectName}`)
        } else {
            store.recentProjects = store.recentProjects.filter(p => p.path !== path)
            localStorage.setItem('recentProjects', JSON.stringify(store.recentProjects))
        }
    }

    // 页面挂载初始化
    onMounted(async () => {
        if (isPlayerMode.value) return

        await store.loadParams()
        if (store.currentProjectPath) {
            projectPathInput.value = store.currentProjectPath
            const ok = await loadProject(store.currentProjectPath)
            if (ok) {
                ElMessage.success(`已自动加载项目: ${store.currentProjectName}`)
            } else {
                ElMessage.warning('自动加载项目失败，请检查路径')
                store.currentProjectPath = null
                projectLoaded.value = false
            }
        }
    })
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
        font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
        background-color: var(--el-bg-color-page);
    }

    #app {
        display: flex;
        flex-direction: column;
        background: var(--el-bg-color-page);
    }

    .welcome {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--el-bg-color-page);
        color: var(--el-text-color-primary);
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
            color: var(--el-text-color-secondary);
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
        color: var(--el-text-color-secondary);
        font-size: 14px;
        margin-bottom: 12px;
    }

        .cached-hint .el-icon {
            color: var(--el-color-primary);
        }

    .recent {
        margin-top: 30px;
        font-size: 14px;
        color: var(--el-text-color-secondary);
    }

        .recent .el-link {
            color: var(--el-color-primary);
        }
</style>