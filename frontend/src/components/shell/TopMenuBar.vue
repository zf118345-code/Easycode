<template>
    <header class="top-menu-bar">
        <div class="menu-brand" aria-label="EasyCode IDE"><Zap :size="17" /><span class="brand-title">EasyCode</span></div>
        <nav class="menu-items-group" aria-label="应用菜单">
            <el-dropdown trigger="click" @command="handleMenuCommand">
<button class="menu-label" type="button">文件</button><template #dropdown>
<el-dropdown-menu>
                <el-dropdown-item command="open">打开项目…</el-dropdown-item><el-dropdown-item command="new-project">新建项目…</el-dropdown-item>
                <el-dropdown-item command="save" divided>立即保存 <span class="shortcut">Ctrl+S</span></el-dropdown-item><el-dropdown-item command="history">版本历史…</el-dropdown-item><el-dropdown-item command="export">导出配置</el-dropdown-item>
                <el-dropdown-item command="close-project" divided>关闭项目</el-dropdown-item>
            </el-dropdown-menu>
</template>
</el-dropdown>
            <el-dropdown trigger="click" @command="handleMenuCommand">
<button class="menu-label" type="button">编辑</button><template #dropdown>
<el-dropdown-menu>
                <el-dropdown-item command="undo">撤销 <span class="shortcut">Ctrl+Z</span></el-dropdown-item><el-dropdown-item command="redo">重做 <span class="shortcut">Ctrl+Y</span></el-dropdown-item>
                <el-dropdown-item command="global-search" divided>全局搜索与引用… <span class="shortcut">Ctrl+P</span></el-dropdown-item>
                <el-dropdown-item command="project-settings" divided>项目设置…</el-dropdown-item><el-dropdown-item command="hotkey-settings">快捷键设置…</el-dropdown-item>
            </el-dropdown-menu>
</template>
</el-dropdown>
            <el-dropdown trigger="click" @command="handleMenuCommand">
<button class="menu-label" type="button">视图</button><template #dropdown>
<el-dropdown-menu>
                <el-dropdown-item command="toggle_minimap">切换全景导航</el-dropdown-item><el-dropdown-item command="auto-layout">自动布局…</el-dropdown-item>
                <el-dropdown-item command="capabilities" divided><Boxes :size="14" />能力库…</el-dropdown-item>
            </el-dropdown-menu>
</template>
</el-dropdown>
            <el-dropdown trigger="click" @command="handleMenuCommand">
<button class="menu-label" type="button">运行</button><template #dropdown>
<el-dropdown-menu>
                <el-dropdown-item command="run_task" :disabled="runDisabled" :title="runDisabled ? runDisabledReason : '从当前选中的单个节点开始执行'"><Play :size="14" />从当前节点执行 <span class="shortcut">F5</span></el-dropdown-item>
                <el-dropdown-item command="schedules"><CalendarClock :size="14" />计划任务…</el-dropdown-item><el-dropdown-item command="runtime-services"><ServerCog :size="14" />运行服务…</el-dropdown-item>
                <el-dropdown-item command="frame-recording" :disabled="recordingDisabled && !recordingActive" divided><Square v-if="recordingActive" :size="13" class="is-danger" /><Video v-else :size="14" />{{ recordingActive ? '停止帧录制' : '帧录制模式' }}</el-dropdown-item>
                <el-dropdown-item command="frame-replay" :disabled="recordingActive || store.isRunning || store.isPaused"><History :size="14" />历史帧工作台…</el-dropdown-item>
            </el-dropdown-menu>
</template>
</el-dropdown>
            <el-dropdown class="optional-menu" trigger="click" @command="handleMenuCommand">
<button class="menu-label" type="button">发布</button><template #dropdown>
<el-dropdown-menu>
                <el-dropdown-item command="open-schema-editor"><Settings :size="14" />Player 配置…</el-dropdown-item><el-dropdown-item command="export-package"><Package :size="14" />发布脚本包…</el-dropdown-item>
            </el-dropdown-menu>
</template>
</el-dropdown>
            <el-dropdown class="optional-menu" trigger="click" @command="handleMenuCommand">
<button class="menu-label" type="button">帮助</button><template #dropdown>
<el-dropdown-menu>
                <el-dropdown-item command="docs">API 文档</el-dropdown-item><el-dropdown-item command="hotkey-settings">快捷键参考</el-dropdown-item>
            </el-dropdown-menu>
</template>
</el-dropdown>
            <el-dropdown class="overflow-menu" trigger="click" @command="handleMenuCommand">
<button class="menu-label compact-menu-label" type="button" aria-label="更多菜单"><MoreHorizontal :size="16" /></button><template #dropdown>
<el-dropdown-menu>
                <el-dropdown-item command="open-schema-editor"><Settings :size="14" />Player 配置…</el-dropdown-item><el-dropdown-item command="export-package"><Package :size="14" />发布脚本包…</el-dropdown-item>
                <el-dropdown-item command="docs" divided>API 文档</el-dropdown-item><el-dropdown-item command="hotkey-settings">快捷键参考</el-dropdown-item>
            </el-dropdown-menu>
</template>
</el-dropdown>
        </nav>

        <div class="context-breadcrumb" :title="breadcrumbTitle"><span>{{ projectName }}</span><ChevronRight v-if="selectionLabel" :size="12" /><strong v-if="selectionLabel">{{ selectionLabel }}</strong></div>
        <div class="canvas-mode-switcher" role="tablist" aria-label="画布模式">
            <button v-for="opt in canvasModeOptions" :key="opt.value" type="button" role="tab" :aria-selected="store.canvasMode === opt.value" :class="{ active: store.canvasMode === opt.value }" @click="handleSwitchCanvasMode(opt.value)"><component :is="opt.icon" :size="13" /><span>{{ opt.label }}</span></button>
        </div>
        <div class="menu-right-actions">
            <div v-if="recordingActive" class="recording-status" title="按 Esc 停止录制"><span />{{ recordingFrames }} 帧<span v-if="recordingFps > 0"> · {{ recordingFps.toFixed(1) }} FPS</span></div>
            <button class="command-button save-indicator" type="button" :class="`is-${projectStore.saveState}`" :title="saveTitle" @click="$emit('saveProject')"><CloudUpload v-if="projectStore.saveState === 'saving'" :size="14" /><CloudAlert v-else-if="projectStore.saveState === 'error'" :size="14" /><Check v-else :size="14" /><span>{{ saveLabel }}</span></button>
            <button class="command-button search-command" type="button" title="全局搜索与引用 (Ctrl+P)" @click="$emit('openGlobalSearch')"><Search :size="15" /><span>搜索</span></button>
            <button class="workspace-button" type="button" :title="`工作面板：${currentWorkspaceName}`" @click="$emit('openSettings')"><Monitor :size="14" /><span>{{ currentWorkspaceName }}</span><ChevronDown :size="11" /></button>
            <el-dropdown trigger="click" @command="handleCaptureCommand">
<button class="command-button capture-button" type="button" :disabled="recordingActive || store.isRunning || store.isPaused" title="快速捕获"><ScanLine :size="15" /><span>捕获</span><ChevronDown :size="11" /></button><template #dropdown>
<el-dropdown-menu>
                <el-dropdown-item command="screenshot"><Camera :size="14" />视觉捕获 <span class="shortcut">Alt+Q</span></el-dropdown-item><el-dropdown-item command="control"><ScanSearch :size="14" />控件捕获 <span class="shortcut">Ctrl+Shift+C</span></el-dropdown-item>
            </el-dropdown-menu>
</template>
</el-dropdown>
        </div>
    </header>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Boxes, Braces, CalendarClock, Camera, Check, ChevronDown, ChevronRight, CloudAlert, CloudUpload, History, Map, Monitor, MoreHorizontal, Package, Play, ScanLine, ScanSearch, Search, ServerCog, Settings, Square, Video, Workflow, Zap } from 'lucide-vue-next'
import { useIdeStore, useProjectStore } from '@/stores'

defineProps({ runDisabled:{type:Boolean,default:false}, recordingActive:{type:Boolean,default:false}, recordingFrames:{type:Number,default:0}, recordingFps:{type:Number,default:0}, recordingDisabled:{type:Boolean,default:false}, runDisabledReason:{type:String,default:''} })
const emit = defineEmits(['run','openSettings','openSchemaEditor','openControlCapture','openHotkeySettings','openScreenshot','openProjectSettings','openProject','newProject','closeProject','saveProject','exportConfig','undo','redo','openDocs','openGlobalSearch','openHistory','autoLayout','toggleFrameRecording','openFrameReplay','publishPackage','openSchedules','openLeftPanel'])
const store = useIdeStore()
const projectStore = useProjectStore()
const canvasModeOptions = [{value:'workflow',label:'主流程',icon:Workflow},{value:'function',label:'函数',icon:Braces},{value:'topology',label:'页面地图',icon:Map}]
const projectName = computed(() => (store.currentProjectPath || '').split(/[/\\]/).pop() || '未打开项目')
const currentGraph = computed(() => store.canvasMode === 'topology'
    ? store.blueprint?.page_map
    : store.canvasMode === 'function'
        ? store.blueprint?.functions?.find(item => item.function_id === store.currentTaskId)?.graph
        : store.blueprint?.main_graph)
const selectionLabel = computed(() => {
    const ids = store.selectedNodeIds || []
    if (ids.length > 1) return `已选 ${ids.length} 个节点`
    const selectedId = ids[0] || store.selectedNodeId
    if (selectedId) { const node=(currentGraph.value?.nodes||[]).find(item=>item.node_id===selectedId); if(node) return `${store.canvasMode === 'topology' ? '页面地图' : store.canvasMode === 'function' ? '函数' : '主流程'} / ${node.node_name || '未命名节点'}` }
    if (store.canvasMode === 'function') return store.blueprint?.functions?.find(item => item.function_id === store.currentTaskId)?.name || ''
    return store.canvasMode === 'topology' ? '页面地图' : '主流程'
})
const breadcrumbTitle = computed(() => [store.currentProjectPath, selectionLabel.value].filter(Boolean).join(' / '))
const currentWorkspaceName = computed(() => store.currentContext?.windowTitle || 'Windows 桌面')
const saveLabel = computed(() => ({saving:'保存中',error:'保存失败',saved:'已保存'}[projectStore.saveState] || '已保存'))
const saveTitle = computed(() => projectStore._lastSaveError?.message || `${saveLabel.value}；点击立即保存`)
const handleSwitchCanvasMode = async mode => {
    if(store.canvasMode===mode)return
    try{
        if(mode === 'function') {
            const target = store.blueprint?.functions?.find(item => item.function_id === store.currentTaskId) || store.blueprint?.functions?.[0]
            if(!target) return ElMessage.info('函数库还是空的，请先从左侧函数库创建函数')
            await store.loadTaskData(target.function_id)
        } else if(mode === 'workflow') await store.loadTaskData('main')
        await store.setCanvasMode(mode)
    }catch(error){console.error('切换画布前自动保存失败:',error);ElMessage.error('自动保存失败，已保留在当前画布')}
}
const handleCaptureCommand = command => emit(command === 'control' ? 'openControlCapture' : 'openScreenshot')
const handleMenuCommand = command => {
    const events={open:'openProject','new-project':'newProject','close-project':'closeProject',save:'saveProject',export:'exportConfig',undo:'undo',redo:'redo',docs:'openDocs','global-search':'openGlobalSearch',history:'openHistory','auto-layout':'autoLayout',run_task:'run',schedules:'openSchedules','frame-recording':'toggleFrameRecording','frame-replay':'openFrameReplay','open-schema-editor':'openSchemaEditor','export-package':'publishPackage','hotkey-settings':'openHotkeySettings','project-settings':'openProjectSettings'}
    if(events[command])emit(events[command]); if(command==='toggle_minimap')store.toggleMinimap(); if(command==='capabilities')emit('openLeftPanel','capabilities'); if(command==='runtime-services')emit('openLeftPanel','runtime')
}
</script>

<style scoped>
.top-menu-bar{height:40px;display:flex;align-items:center;gap:10px;padding:0 10px;flex-shrink:0;border-bottom:1px solid var(--app-separator);background:var(--app-bg-chrome);user-select:none}.menu-brand{display:flex;align-items:center;gap:6px;flex:0 0 auto;color:var(--app-text-primary);font-size:12px;font-weight:650}.menu-brand svg{color:var(--app-color-primary)}.menu-items-group{display:flex;align-items:center;gap:1px}.menu-label{height:28px;padding:0 7px;border:0;border-radius:5px;background:transparent;color:var(--app-text-regular);cursor:pointer}.menu-label:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}.compact-menu-label{display:grid;place-items:center;width:28px;padding:0}.overflow-menu{display:none}.shortcut{margin-left:22px;color:var(--app-text-secondary);font-size:10px}.context-breadcrumb{min-width:0;max-width:300px;display:flex;align-items:center;gap:5px;overflow:hidden;color:var(--app-text-secondary);font-size:11px;white-space:nowrap}.context-breadcrumb span,.context-breadcrumb strong{overflow:hidden;text-overflow:ellipsis}.context-breadcrumb strong{color:var(--app-text-regular);font-weight:500}.canvas-mode-switcher{display:flex;align-items:center;gap:2px;padding:2px;flex:0 0 auto;border:1px solid var(--app-border-default);border-radius:7px;background:var(--app-bg-input)}.canvas-mode-switcher button{height:24px;display:flex;align-items:center;gap:4px;padding:0 9px;border:0;border-radius:5px;background:transparent;color:var(--app-text-secondary);font-size:11px;cursor:pointer}.canvas-mode-switcher button:hover{color:var(--app-text-primary)}.canvas-mode-switcher button.active{background:var(--app-bg-raised);color:var(--app-text-primary);box-shadow:inset 0 0 0 1px var(--app-border-strong)}.menu-right-actions{min-width:0;margin-left:auto;display:flex;align-items:center;gap:5px}.command-button,.workspace-button{height:28px;display:flex;align-items:center;gap:5px;padding:0 8px;border:1px solid transparent;border-radius:6px;background:transparent;color:var(--app-text-secondary);font-size:11px;cursor:pointer;white-space:nowrap}.command-button:hover:not(:disabled),.workspace-button:hover{border-color:var(--app-border-default);background:var(--app-bg-hover);color:var(--app-text-primary)}.command-button:disabled{opacity:.4;cursor:not-allowed}.save-indicator.is-saved{color:var(--app-color-success)}.save-indicator.is-saving{color:var(--app-color-warning)}.save-indicator.is-error{color:var(--app-color-danger)}.workspace-button{max-width:190px;border-color:var(--app-border-default);background:var(--app-bg-raised)}.workspace-button span{overflow:hidden;text-overflow:ellipsis}.capture-button{border-color:var(--app-border-default);color:var(--app-text-regular)}.recording-status{display:flex;align-items:center;gap:5px;color:var(--app-color-danger);font-size:10px;white-space:nowrap}.recording-status>span:first-child{width:7px;height:7px;border-radius:50%;background:currentColor}.is-danger{color:var(--app-color-danger);fill:currentColor}@media(max-width:1260px){.context-breadcrumb{max-width:180px}.search-command span,.save-indicator span{display:none}}@media(max-width:1040px){.optional-menu,.brand-title{display:none}.overflow-menu{display:inline-flex}.workspace-button{max-width:130px}}@media(max-width:820px){.context-breadcrumb{display:none}.canvas-mode-switcher button span,.capture-button span{display:none}}
</style>
