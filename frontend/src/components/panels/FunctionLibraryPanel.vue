<template>
    <section class="function-panel" @click="closeMenus">
        <header class="panel-toolbar">
            <label><Search :size="13" /><input v-model="query" placeholder="搜索函数" /></label>
            <button type="button" title="新建函数文件夹" aria-label="新建函数文件夹" @click="createFolder"><FolderPlus :size="15" /></button>
            <button class="primary" type="button" title="新建函数" aria-label="新建函数" @click="createFunction"><Plus :size="15" /></button>
            <el-dropdown trigger="click" @command="libraryAction">
                <button type="button" title="函数库操作" aria-label="函数库操作"><MoreHorizontal :size="15" /></button>
                <template #dropdown><el-dropdown-menu><el-dropdown-item command="import"><FileInput :size="14" />导入 .ecf</el-dropdown-item></el-dropdown-menu></template>
            </el-dropdown>
        </header>

        <div class="function-tree" role="tree" aria-label="函数库">
            <div v-for="folder in folders" :key="folder.folder_id" class="function-folder">
                <button class="folder-row" type="button" @click="toggleFolder(folder.folder_id)" @dblclick.stop="renameFolder(folder)" @contextmenu.prevent="openFolderMenu($event, folder)">
                    <ChevronRight :class="{ expanded: !collapsed.has(folder.folder_id) }" :size="13" /><FolderCode :size="14" /><span>{{ folder.name }}</span><small>{{ functionsFor(folder.folder_id).length }}</small>
                </button>
                <FunctionRow v-for="fn in collapsed.has(folder.folder_id) ? [] : functionsFor(folder.folder_id)" :key="fn.function_id" :item="fn" :active="activeFunctionId === fn.function_id" nested @open="openFunction" @menu="openFunctionMenu" />
            </div>

            <div v-if="unfiledFunctions.length" class="unfiled">
                <div class="section-label"><Braces :size="12" /><span>函数</span><small>{{ unfiledFunctions.length }}</small></div>
                <FunctionRow v-for="fn in unfiledFunctions" :key="fn.function_id" :item="fn" :active="activeFunctionId === fn.function_id" @open="openFunction" @menu="openFunctionMenu" />
            </div>

            <div v-if="!visibleFunctionCount" class="empty-state">
                <Braces :size="24" />
                <strong>{{ query ? '没有匹配函数' : '还没有函数' }}</strong>
                <span>函数拥有独立画布和显式契约。创建后即可在右侧函数检查器中配置。</span>
                <button v-if="!query" type="button" @click="createFunction"><Plus :size="13" />新建函数</button>
            </div>
        </div>

        <div v-if="context.visible" class="function-menu" role="menu" aria-label="函数操作" :style="{ left: `${context.x}px`, top: `${context.y}px` }" @click.stop>
            <button type="button" role="menuitem" @click="renameFunction(context.target)"><Pencil :size="14" />重命名</button>
            <button type="button" role="menuitem" @click="duplicateFunction(context.target)"><CopyPlus :size="14" />创建副本</button>
            <button type="button" role="menuitem" @click="moveFunction(context.target)"><FolderInput :size="14" />移动到文件夹…</button>
            <button type="button" role="menuitem" @click="exportFunction(context.target)"><FileOutput :size="14" />导出 .ecf</button>
            <button type="button" role="menuitem" class="danger" @click="deleteFunction(context.target)"><Trash2 :size="14" />删除函数</button>
        </div>
        <div v-if="folderContext.visible" class="function-menu" role="menu" aria-label="函数文件夹操作" :style="{ left: `${folderContext.x}px`, top: `${folderContext.y}px` }" @click.stop>
            <button type="button" role="menuitem" @click="renameFolder(folderContext.target)"><Pencil :size="14" />重命名文件夹</button>
            <button type="button" role="menuitem" class="danger" @click="deleteFolder(folderContext.target)"><Trash2 :size="14" />删除文件夹</button>
        </div>
    </section>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Braces, ChevronRight, CopyPlus, FileInput, FileOutput, FolderCode, FolderInput, FolderPlus, MoreHorizontal, Pencil, Plus, Search, Trash2 } from 'lucide-vue-next'
import { useIdeStore } from '@/stores'
import { blueprintApi } from '@/api/blueprintApi'
import { projectWorkspaceApi } from '@/api/projectWorkspaceApi'
import { downloadBlob, safeDownloadName } from '@/utils/download'
import { collectFunctionReferences, createStableId } from '@/utils/flowModel'
import { notifyActionError } from '@/utils/userActionErrors'

const FunctionRow = defineComponent({
    props: {
        item: { type: Object, default: () => ({}) },
        active: { type: Boolean, default: false },
        nested: { type: Boolean, default: false }
    },
    emits: ['open', 'menu'],
    setup(props, { emit }) {
        return () => h('button', {
            class: ['function-row', { active: props.active, nested: props.nested }],
            type: 'button',
            onClick: () => emit('open', props.item),
            onContextmenu: event => { event.preventDefault(); emit('menu', event, props.item) }
        }, [h(Braces, { size: 14 }), h('span', props.item.name), h('small', `${props.item.graph?.nodes?.length || 0}`)])
    }
})

const store = useIdeStore()
const query = ref('')
const collapsed = ref(new Set())
const context = reactive({ visible: false, x: 0, y: 0, target: null })
const folderContext = reactive({ visible: false, x: 0, y: 0, target: null })
const activeFunctionId = computed(() => store.canvasMode === 'function' && !store.functionWorkspaceEmpty ? store.currentTaskId : '')
const matches = item => !query.value.trim() || `${item.name} ${item.description || ''}`.toLowerCase().includes(query.value.trim().toLowerCase())
const folders = computed(() => store.blueprint?.function_folders || [])
const functionsFor = folderId => (store.blueprint?.functions || []).filter(item => item.folder_id === folderId && matches(item))
const unfiledFunctions = computed(() => (store.blueprint?.functions || []).filter(item => !item.folder_id && matches(item)))
const visibleFunctionCount = computed(() => folders.value.reduce((count, folder) => count + functionsFor(folder.folder_id).length, 0) + unfiledFunctions.value.length)

function closeMenus() { context.visible = false; folderContext.visible = false }
function onGlobalPointerDown(event) {
    if (!event.target?.closest?.('.function-menu')) closeMenus()
}
function onGlobalKeyDown(event) {
    if (event.key === 'Escape') closeMenus()
}
function uniqueFunctionName(raw, excludedId = '') {
    const used = new Set((store.blueprint?.functions || []).filter(item => item.function_id !== excludedId).map(item => item.name))
    const base = String(raw || '新建函数').trim() || '新建函数'
    if (!used.has(base)) return base
    let suffix = 1
    while (used.has(`${base}${suffix}`)) suffix += 1
    return `${base}${suffix}`
}

function toggleFolder(id) {
    const next = new Set(collapsed.value)
    next.has(id) ? next.delete(id) : next.add(id)
    collapsed.value = next
}

async function openFunction(item) {
    if (!item?.function_id) return
    try {
        await store.navigateToGraph('function', item.function_id)
        store.updateUiState('rightPanelExpanded', true)
        store.setFocusTarget({ type: 'graph', id: item.function_id, timestamp: Date.now() })
        closeMenus()
    } catch (error) {
        notifyActionError(error, '无法打开函数')
    }
}

async function createFunction() {
    try {
        const result = await ElMessageBox.prompt('函数会创建独立画布，并包含固定入口和显式返回节点。', '新建函数', { inputValue: '新建函数', inputPattern: /\S+/, inputErrorMessage: '名称不能为空', confirmButtonText: '创建', cancelButtonText: '取消' })
        const created = await store.createFunction(result.value.trim())
        await openFunction(created)
    } catch (error) { notifyActionError(error, '创建函数失败') }
}

async function createFolder() {
    try {
        const result = await ElMessageBox.prompt('文件夹只整理函数库，不改变执行语义。', '新建函数文件夹', { inputValue: '新建文件夹', inputPattern: /\S+/, inputErrorMessage: '名称不能为空', confirmButtonText: '创建', cancelButtonText: '取消' })
        const names = new Set(folders.value.map(item => item.name))
        let name = result.value.trim(), suffix = 1
        const base = name
        while (names.has(name)) name = `${base}${suffix++}`
        store.blueprint.function_folders.push({ folder_id: createStableId('folder'), name })
        await store.saveWorkflowImmediately()
    } catch (error) { notifyActionError(error, '创建函数文件夹失败') }
}

async function renameFolder(folder) {
    folderContext.visible = false
    try {
        const result = await ElMessageBox.prompt('', '重命名函数文件夹', { inputValue: folder.name, inputPattern: /\S+/, inputErrorMessage: '名称不能为空' })
        const used = new Set(folders.value.filter(item => item.folder_id !== folder.folder_id).map(item => item.name))
        let name = result.value.trim(), suffix = 1
        const base = name
        while (used.has(name)) name = `${base}${suffix++}`
        folder.name = name
        await store.saveWorkflowImmediately()
    } catch (error) { notifyActionError(error, '重命名函数文件夹失败') }
}

function openFolderMenu(event, folder) {
    context.visible = false
    Object.assign(folderContext, { visible: true, x: event.clientX, y: event.clientY, target: folder })
}

async function deleteFolder(folder) {
    folderContext.visible = false
    if (!folder) return
    const count = (store.blueprint?.functions || []).filter(item => item.folder_id === folder.folder_id).length
    try {
        await ElMessageBox.confirm(count ? `删除文件夹“${folder.name}”？其中 ${count} 个函数会移到未分类，函数本身不会删除。` : `删除空文件夹“${folder.name}”？`, '删除函数文件夹', { type: 'warning', confirmButtonText: '删除文件夹', cancelButtonText: '取消' })
        for (const fn of store.blueprint.functions || []) if (fn.folder_id === folder.folder_id) fn.folder_id = null
        store.blueprint.function_folders = folders.value.filter(item => item.folder_id !== folder.folder_id)
        await store.saveWorkflowImmediately()
    } catch (error) { notifyActionError(error, '删除函数文件夹失败') }
}

function openFunctionMenu(event, item) {
    folderContext.visible = false
    Object.assign(context, { visible: true, x: event.clientX, y: event.clientY, target: item })
}

async function renameFunction(item) {
    context.visible = false
    try {
        const result = await ElMessageBox.prompt('', '重命名函数', { inputValue: item.name, inputPattern: /\S+/, inputErrorMessage: '名称不能为空' })
        item.name = uniqueFunctionName(result.value, item.function_id)
        await store.saveFunctionData(item)
    } catch (error) { notifyActionError(error, '重命名函数失败') }
}

async function duplicateFunction(item) {
    context.visible = false
    try {
        const copy = await store.projectStore.duplicateFunction(item.function_id)
        await openFunction(copy)
        ElMessage.success('函数副本已创建')
    } catch (error) { ElMessage.error(error.message || '复制失败') }
}

async function moveFunction(item) {
    context.visible = false
    const options = [{ value: '', label: '不放入文件夹' }, ...folders.value.map(folder => ({ value: folder.folder_id, label: folder.name }))]
    try {
        const result = await ElMessageBox.prompt(`可用文件夹：${options.map(option => option.label).join('、')}`, '移动函数', { inputValue: options.find(option => option.value === item.folder_id)?.label || '不放入文件夹' })
        const target = options.find(option => option.label === result.value.trim())
        if (!target) return ElMessage.warning('请输入现有文件夹名称')
        item.folder_id = target.value || null
        await store.saveFunctionData(item)
    } catch (error) { notifyActionError(error, '移动函数失败') }
}

async function exportFunction(item) {
    context.visible = false
    try {
        const blob = await blueprintApi.exportFunction(item.function_id, store.currentProjectPath)
        downloadBlob(blob, `${safeDownloadName(item.name, 'function')}.ecf`)
    } catch (error) { ElMessage.error(error.message || '导出失败') }
}

async function deleteFunction(item) {
    context.visible = false
    const refs = collectFunctionReferences(store.blueprint, item.function_id)
    if (refs.length) return ElMessage.warning(`该函数仍被 ${refs.length} 个调用节点使用`)
    try {
        await ElMessageBox.confirm(`删除函数“${item.name}”？此操作不可通过画布撤销。`, '删除函数', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
        const wasOpen = activeFunctionId.value === item.function_id
        await store.deleteFunction(item.function_id)
        if (wasOpen) store.enterFunctionLibrary()
    } catch (error) { notifyActionError(error, '删除函数失败') }
}

async function libraryAction(command) {
    if (command !== 'import') return
    try {
        const picked = await projectWorkspaceApi.chooseFile('选择 EasyCode 函数包', ['.ecf'])
        if (!picked?.path) return
        const result = await blueprintApi.importFunction(store.currentProjectPath, picked.path)
        await store.loadProjectData()
        const imported = (store.blueprint?.functions || []).find(item => item.function_id === result.root_function_id)
        if (imported) await openFunction(imported)
        ElMessage.success(`已导入 ${result.imported || 1} 个函数，所有 ID 已重新生成`)
    } catch (error) { ElMessage.error(error.message || '导入失败') }
}

onMounted(() => {
    window.addEventListener('easycode:create-function', createFunction)
    window.addEventListener('pointerdown', onGlobalPointerDown)
    window.addEventListener('keydown', onGlobalKeyDown)
})
onUnmounted(() => {
    window.removeEventListener('easycode:create-function', createFunction)
    window.removeEventListener('pointerdown', onGlobalPointerDown)
    window.removeEventListener('keydown', onGlobalKeyDown)
})
</script>

<style scoped>
.function-panel{height:100%;min-width:0;display:grid;grid-template-rows:40px minmax(0,1fr);background:var(--app-sidebar-bg);color:var(--app-text-primary);font-size:11px}.panel-toolbar{display:flex;align-items:center;gap:3px;padding:0 7px;border-bottom:1px solid var(--app-separator)}.panel-toolbar label{min-width:0;flex:1;height:29px;display:flex;align-items:center;gap:6px;padding:0 7px;border:1px solid var(--app-border-default);border-radius:6px;background:var(--app-input-bg)}.panel-toolbar label:focus-within{border-color:var(--el-color-primary);box-shadow:var(--focus-ring)}.panel-toolbar input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:inherit;font:inherit}.panel-toolbar button{width:28px;height:28px;display:grid;place-items:center;padding:0;border:1px solid transparent;border-radius:6px;background:transparent;color:var(--app-text-secondary);cursor:pointer}.panel-toolbar button:hover{border-color:var(--app-border-default);background:var(--el-fill-color-light);color:var(--app-text-primary)}.panel-toolbar button.primary{border-color:var(--el-color-primary);background:var(--el-color-primary);color:var(--app-color-on-primary)}.panel-toolbar :deep(.el-dropdown){height:28px;flex:0 0 auto}.function-tree{min-height:0;overflow:auto;padding:6px}.folder-row,.function-row{width:100%;height:29px;display:flex;align-items:center;gap:7px;padding:0 7px;border:0;border-radius:5px;background:transparent;color:var(--app-text-secondary);text-align:left;cursor:pointer}.folder-row:hover,.function-row:hover,.function-row.active{background:var(--el-fill-color-light);color:var(--app-text-primary)}.function-row.active{box-shadow:inset 2px 0 var(--el-color-primary)}.folder-row>svg:first-child{transition:transform .12s}.folder-row>svg.expanded{transform:rotate(90deg)}.folder-row span,.function-row span{min-width:0;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.folder-row small,.function-row small,.section-label small{color:var(--app-text-placeholder);font-size:10px}.function-row.nested{padding-left:27px}.section-label{height:27px;display:flex;align-items:center;gap:6px;padding:0 8px;color:var(--app-text-placeholder)}.section-label span{flex:1}.empty-state{min-height:210px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;padding:20px;color:var(--app-text-placeholder);text-align:center}.empty-state strong{color:var(--app-text-secondary)}.empty-state span{max-width:220px;line-height:1.5}.empty-state button{display:flex;align-items:center;gap:5px;margin-top:4px;padding:6px 9px;border:0;border-radius:6px;background:var(--app-color-primary-dim);color:var(--el-color-primary);cursor:pointer}.function-menu{position:fixed;z-index:6500;min-width:185px;padding:5px;border:1px solid var(--app-overlay-border);border-radius:var(--app-radius-md);background:var(--app-overlay-bg);box-shadow:var(--app-shadow-md)}.function-menu button{width:100%;height:30px;display:flex;align-items:center;gap:8px;padding:0 8px;border:0;border-radius:5px;background:transparent;color:var(--app-text-primary);font-size:11px;text-align:left;cursor:pointer}.function-menu button:hover{background:var(--el-fill-color-light)}.function-menu button.danger{color:var(--el-color-danger)}
</style>
