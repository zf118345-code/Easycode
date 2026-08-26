<template>
    <div id="app" @contextmenu.prevent>
        <IdeLayout v-if="store.currentProjectPath && projectLoaded" />

        <div v-else class="welcome">
            <div class="welcome-content">
                <h1><Zap :size="28" /> Easycode 自动化工作台</h1>
                <p>每个文件夹都是一个完全独立的脚本项目</p>

                <div class="open-section">
                    <div class="welcome-actions">
                        <el-button type="primary" size="large" :loading="store.workspaceBusy" @click="handleOpenProject">
                            <FolderOpen :size="18" />打开项目
                        </el-button>
                        <el-button size="large" :disabled="store.workspaceBusy" @click="handleNewProject">
                            <FolderPlus :size="18" />新建项目
                        </el-button>
                    </div>
                </div>

                <div v-if="store.recentProjects?.length" class="recent">
                    <div class="recent-title">最近项目</div>
                    <div v-for="project in visibleRecentProjects" :key="project.path" class="recent-item">
                        <button type="button" class="recent-open" :disabled="project.missing || store.workspaceBusy" @click="handleOpenRecent(project)">
                            <Folder :size="15" />
                            <span class="recent-name">{{ project.name }}</span>
                            <span class="recent-path">{{ project.path }}</span>
                            <span v-if="project.missing" class="missing-badge">路径已失效</span>
                        </button>
                        <button type="button" class="recent-remove" title="从最近项目移除" aria-label="从最近项目移除" @click="handleRemoveRecent(project.path)">
                            <X :size="14" />
                        </button>
                    </div>
                    <button
                        v-if="store.recentProjects.length > RECENT_COLLAPSED_COUNT"
                        type="button"
                        class="recent-toggle"
                        @click="showAllRecent = !showAllRecent">
                        {{ showAllRecent ? '收起' : `显示其余 ${store.recentProjects.length - RECENT_COLLAPSED_COUNT} 个项目` }}
                    </button>
                </div>
            </div>
        </div>
        <ProjectCreateDialog v-model="createDialogVisible" @created="projectLoaded = true" />
    </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Folder, FolderOpen, FolderPlus, X, Zap } from 'lucide-vue-next'
import { useProjectStore } from '@/stores'
import IdeLayout from '@/layouts/IdeLayout.vue'
import ProjectCreateDialog from '@/components/ProjectCreateDialog.vue'
import { useProjectEntryActions } from '@/composables/useProjectEntryActions'

const store = useProjectStore()
const projectLoaded = ref(false)
const createDialogVisible = ref(false)
const showAllRecent = ref(false)
const RECENT_COLLAPSED_COUNT = 6
const visibleRecentProjects = computed(() => showAllRecent.value
    ? store.recentProjects
    : store.recentProjects.slice(0, RECENT_COLLAPSED_COUNT))
const { openProjectPath, chooseAndOpenProject } = useProjectEntryActions()

const handleOpenProject = async () => {
    projectLoaded.value = await chooseAndOpenProject()
}

const handleNewProject = () => { createDialogVisible.value = true }

const handleOpenRecent = async (project) => {
    if (project.missing) return ElMessage.warning('项目路径已失效，请重新打开移动后的文件夹')
    projectLoaded.value = await openProjectPath(project.path)
}

const handleRemoveRecent = async (path) => {
    try { await store.removeRecentProject(path) } catch (error) { ElMessage.error(error.message) }
}

onMounted(async () => {
    await store.loadParams()
    try {
        const result = await store.restoreLastProject()
        projectLoaded.value = Boolean(result?.workspace)
        if (projectLoaded.value) ElMessage.success(`已恢复项目: ${store.currentProjectName}`)
    } catch {
        projectLoaded.value = false
        await store.loadRecentProjects().catch(() => {})
        ElMessage.warning('上次项目无法恢复，请重新选择项目文件夹')
    }
})
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; overflow: hidden; font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; background: var(--el-bg-color-page); }
#app { display: flex; flex-direction: column; }
.welcome { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--el-text-color-primary); background: radial-gradient(circle at 50% 37%, rgba(217, 84, 23, .075), transparent 34%), var(--app-bg-base); }
.welcome-content { width: min(680px, calc(100vw - 48px)); max-height: calc(100vh - 60px); overflow: auto; padding: 40px; }
.welcome-content h1 { display: flex; align-items: center; justify-content: center; gap: 9px; font-size: 28px; line-height: 36px; font-weight: 600; letter-spacing: -.025em; margin-bottom: 8px; }
.welcome-content h1 svg { color: var(--el-color-primary); }
.welcome-content > p { text-align: center; font-size: 13px; line-height: 20px; color: var(--el-text-color-secondary); margin-bottom: 28px; }
.open-section { display: flex; flex-direction: column; align-items: stretch; }
.welcome-actions { display: flex; justify-content: center; gap: 8px; margin-top: 8px; }
.welcome-actions .el-button svg { margin-right: 5px; }
.recent { margin-top: 28px; padding: 8px; border: 1px solid var(--app-border-default); border-radius: 12px; background: var(--app-bg-panel); }
.recent-title { color: var(--el-text-color-secondary); font-size: 11px; line-height: 16px; padding: 4px 8px 8px; }
.recent-item { display: flex; align-items: center; border-radius: 8px; }
.recent-item:hover { background: var(--el-fill-color-light); }
.recent-open { min-width: 0; min-height: 36px; flex: 1; display: grid; grid-template-columns: 20px minmax(90px, 160px) 1fr auto; align-items: center; gap: 8px; border: 0; background: transparent; color: var(--el-text-color-primary); text-align: left; padding: 8px 10px; cursor: pointer; }
.recent-open:disabled { cursor: default; opacity: .55; }
.recent-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recent-path { color: var(--el-text-color-secondary); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.missing-badge { color: var(--el-color-warning); font-size: 11px; }
.recent-remove { border: 0; background: transparent; color: var(--el-text-color-secondary); cursor: pointer; display: inline-flex; padding: 8px; }
.recent-remove:hover { color: var(--el-color-danger); }
.recent-toggle { width:100%; min-height:32px; margin-top:3px; border:0; border-top:1px solid var(--app-separator); background:transparent; color:var(--app-text-secondary); font-size:11px; cursor:pointer; }
.recent-toggle:hover { color:var(--app-text-primary); }
</style>
