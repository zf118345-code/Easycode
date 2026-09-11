<!-- frontend/src/components/FileBrowser.vue -->
<template>
    <div class="file-browser dark-theme" :class="{ 'is-fill-height': fillHeight }">
        <!-- 左侧目录树区域 -->
        <div class="tree-sidebar">
            <div class="tree-header">
                <span><Folder :size="16" style="vertical-align: middle;" /> 资源分类</span>
                <el-button v-if="!isVNext" class="trash-button" link size="small" title="资源回收站" @click="openTrashDialog">
                    <ArchiveRestore :size="14" /> 回收站
                </el-button>
            </div>

            <div class="tree-wrapper">
                <el-tree
ref="treeRef"
                         :data="treeData"
                         :props="defaultProps"
                         node-key="id"
                         highlight-current
                         default-expand-all
                         :expand-on-click-node="false"
                         @node-click="handleFolderClick">
                    <template #default="{ node, data }">
                        <div class="custom-tree-node">
                            <template v-if="data.isCreating">
                                <Folder :size="14" class="node-icon" />
                                <input
ref="inlineInputRef"
                                       v-model="data.creatingName"
                                       class="inline-folder-input"
                                       @keyup.enter="submitInlineFolder(data)"
                                       @keyup.esc="cancelInlineFolder(data)"
                                       @blur="submitInlineFolder(data)" />
                            </template>
                            <template v-else>
                                <span class="node-label">
                                    <Folder :size="14" style="vertical-align: middle;" /> {{ node.label }}
                                </span>
                                <span class="node-actions" @click.stop>
                                    <el-button
                                        v-if="data.id"
                                        class="node-icon-btn"
                                        link
                                        size="small"
                                        title="新建子文件夹"
                                        @click.stop="inlineCreateFolder(data.id)">
                                        <FolderPlus :size="14" />
                                    </el-button>
                                    <LockKeyhole v-if="data.protected" :size="13" class="protected-icon" />
                                    <el-dropdown v-else-if="data.id" trigger="click" @command="command => handleFolderCommand(command, data)">
                                        <el-button class="node-icon-btn" link size="small" title="文件夹操作" @click.stop>
                                            <MoreHorizontal :size="15" />
                                        </el-button>
                                        <template #dropdown>
                                            <el-dropdown-menu>
                                                <el-dropdown-item command="move"><FolderInput :size="14" /> 移动或重命名</el-dropdown-item>
                                                <el-dropdown-item command="delete" divided><Trash2 :size="14" /> 删除文件夹</el-dropdown-item>
                                            </el-dropdown-menu>
                                        </template>
                                    </el-dropdown>
                                </span>
                            </template>
                        </div>
                    </template>
                </el-tree>
            </div>
        </div>

        <!-- 右侧内容与操作区 -->
        <div class="content-body">
            <div class="location-bar">
                <span>当前选择路径: </span>
                <strong class="path-highlight">{{ resourceRootLabel }}/{{ currentRelPath || '(根目录)' }}</strong>
            </div>

            <!-- 图片网格查看 -->
            <div class="image-grid" role="listbox" aria-label="项目图片资源" @scroll.passive="handleImageGridScroll">
                <div
v-for="img in displayedImages"
                     :key="img.name"
                     class="image-card"
                     :class="{ selected: selectedImage === img.name }"
                     role="option"
                     tabindex="0"
                     :aria-selected="selectedImage === img.name"
                     :aria-label="img.name"
                     @click="handleImageClick(img)"
                     @keydown.space.prevent="handleImageClick(img)"
                     @keydown.enter.prevent="handleImageKeyboard(img)"
                     @dblclick="handleImageDblClick(img)">
                    <div class="img-wrapper">
                        <img v-if="img.data" :src="img.data" :alt="img.name" loading="lazy" decoding="async" />
                        <div v-if="isManageMode" class="image-actions" @click.stop>
                            <el-button circle size="small" title="移动或重命名" @click.stop="openMoveDialog(img, 'file')">
                                <FolderInput :size="14" />
                            </el-button>
                            <el-button circle size="small" type="danger" title="删除图片" @click.stop="confirmDelete(img.relative_path)">
                                <Trash2 :size="14" />
                            </el-button>
                        </div>
                    </div>
                    <div class="image-name" :title="img.name">{{ img.name }}</div>
                </div>
                <div v-if="!imageList.length" class="empty-tip">
                    <FolderOpen :size="16" style="vertical-align: middle;" /> 当前目录下暂无图片，可在下方直接输入新名称保存
                </div>
            </div>

            <!-- 底部保存/选择操作栏 -->
            <div v-if="isSaveMode" class="action-footer">
                <div class="input-group">
                    <span class="input-label">图片名称:</span>
                    <el-input
v-model="saveFileName"
                              :placeholder="allowEmptyName ? '可留空并自动生成不重复名称' : '点击图片复制名，或输入新名称'"
                              :disabled="savePending"
                              clearable
                              style="width: 300px;"
                              @keyup.enter="handleSaveCheck" />
                </div>
                <div class="btn-group">
                    <el-button :disabled="savePending" @click="$emit('close')">取消</el-button>
                    <el-button type="primary" :loading="savePending" @click="handleSaveCheck">{{ saveButtonText }}</el-button>
                </div>
            </div>

            <div v-else-if="!isManageMode" class="action-footer">
                <span class="tip-text"><Lightbulb :size="14" style="vertical-align: middle;" /> 单击填充名，双击直接确认选择</span>
                <div class="btn-group">
                    <el-button type="info" @click="$emit('close')">取消</el-button>
                    <el-button type="success" :disabled="!selectedImage" @click="confirmSelect">
                        确定选择
                    </el-button>
                </div>
            </div>
        </div>

        <el-dialog
            v-model="moveDialogVisible"
            title="移动或重命名资源"
            width="460px"
            append-to-body
            :close-on-click-modal="false">
            <div class="move-form">
                <label>当前资源</label>
                <div class="move-source">/templates/{{ moveEntry?.path }}</div>
                <label>目标文件夹</label>
                <el-select v-model="moveTargetParent" filterable style="width: 100%;" placeholder="选择目标文件夹">
                    <el-option
                        v-for="folder in moveDestinations"
                        :key="folder.id"
                        :label="folder.label"
                        :value="folder.id"
                        :disabled="folder.disabled" />
                </el-select>
                <label>新名称</label>
                <el-input v-model="moveName" maxlength="160" show-word-limit @keyup.enter="submitMove" />
            </div>
            <template #footer>
                <el-button @click="moveDialogVisible = false">取消</el-button>
                <el-button type="primary" :loading="mutationPending" :disabled="!moveTargetParent || !moveName.trim()" @click="submitMove">
                    确认移动
                </el-button>
            </template>
        </el-dialog>

        <el-dialog
            v-model="trashDialogVisible"
            title="资源回收站"
            width="620px"
            append-to-body
            :close-on-click-modal="false">
            <div class="trash-caption">
                删除的资源最多保留 {{ trashRetentionDays }} 天或共 {{ formatBytes(trashMaxBytes) }}；恢复不会自动重绑已清空的节点。
            </div>
            <div v-loading="trashLoading" class="trash-list">
                <div v-if="!trashEntries.length && !trashLoading" class="trash-empty">回收站为空</div>
                <div v-for="entry in trashEntries" :key="entry.transaction_id" class="trash-entry">
                    <div class="trash-entry-main">
                        <div class="trash-path">/templates/{{ entry.original_path }}</div>
                        <div class="trash-meta">
                            {{ formatTrashTime(entry.deleted_at) }} · {{ formatBytes(entry.size_bytes) }} · {{ entry.asset_records ? Object.keys(entry.asset_records).length : 0 }} 项资源
                        </div>
                    </div>
                    <el-button
                        size="small"
                        type="primary"
                        plain
                        :disabled="!entry.restorable || restoringTrashId === entry.transaction_id"
                        :loading="restoringTrashId === entry.transaction_id"
                        @click="restoreTrashEntry(entry)">
                        <RotateCcw :size="14" /> {{ entry.restorable ? '恢复' : '原位置已占用' }}
                    </el-button>
                </div>
            </div>
            <template #footer>
                <el-button @click="trashDialogVisible = false">关闭</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script setup>
    import { ref, watch, nextTick, computed, h, onBeforeUnmount } from 'vue'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import {
        ArchiveRestore, Folder, FolderOpen, FolderInput, FolderPlus, Lightbulb,
        LockKeyhole, MoreHorizontal, RotateCcw, Trash2
    } from 'lucide-vue-next'
    import { visionApi } from '@/api/visionApi'
    import { vnextApi } from '@/vnext/api'
    import { useProjectStore } from '@/stores/projectStore'
    import { publishResourceMutation } from '@/utils/resourceMutationEvents'

    const props = defineProps({
        projectPath: { type: String, required: true },
        mode: { type: String, default: 'select' },
        initialPath: { type: String, default: '' },
        allowEmptyName: { type: Boolean, default: false },
        saveButtonText: { type: String, default: '保存截图' },
        saveBusy: { type: Boolean, default: false },
        fillHeight: { type: Boolean, default: false },
        workspaceKind: { type: String, default: 'legacy' },
        workspaceIdentity: { type: Object, default: null }
    })

    const emit = defineEmits(['select', 'save', 'close', 'mutated'])
    const projectStore = useProjectStore()

    const flushProjectBeforeMutation = async () => {
        if (projectStore.currentProjectPath && projectStore.currentProjectPath === props.projectPath) {
            await projectStore.flushPendingSaves()
        }
    }

    const isSaveMode = computed(() => props.mode === 'save' || props.mode === 'capture-save')
    const isCaptureSaveMode = computed(() => props.mode === 'capture-save')
    const isManageMode = computed(() => props.mode === 'manage')
    const isVNext = computed(() => props.workspaceKind === 'vnext' && props.workspaceIdentity)
    const resourceRootLabel = computed(() => isVNext.value ? '/assets' : '/templates')

    const treeRef = ref(null)
    const inlineInputRef = ref(null)

    const MANAGED_ROOT_NAMES = Object.freeze(['image', 'ocr', 'page'])
    const createManagedRoots = () => MANAGED_ROOT_NAMES.map(rootName => ({
        name: rootName,
        id: rootName,
        type: 'directory',
        children: [],
        protected: true
    }))

    // 不等待接口才显示基础结构。独立捕获 WebView 即便短时断网或工作区
    // 身份失效，也不能退化成误导用户的 “No Data”。
    const treeData = ref(createManagedRoots())
    const imageList = ref([])
    const renderedImageCount = ref(80)
    const displayedImages = computed(() => imageList.value.slice(0, renderedImageCount.value))
    const currentRelPath = ref('')
    const selectedImage = ref('')
    const selectedAsset = ref(null)
    const saveFileName = ref('')
    const saving = ref(false)
    const savePending = computed(() => saving.value || props.saveBusy)
    const mutationPending = ref(false)
    const moveDialogVisible = ref(false)
    const moveEntry = ref(null)
    const moveTargetParent = ref('')
    const moveName = ref('')
    const trashDialogVisible = ref(false)
    const trashLoading = ref(false)
    const trashEntries = ref([])
    const trashRetentionDays = ref(30)
    const trashMaxBytes = ref(0)
    const restoringTrashId = ref('')
    let previewGeneration = 0
    let vnextAssets = []

    const previewBatchSize = () => isCaptureSaveMode.value ? 16 : 80

    const defaultProps = { children: 'children', label: 'name' }

    const flattenFolders = (nodes, depth = 0) => {
        const result = []
        for (const node of nodes || []) {
            if (node.id) {
                result.push({ id: node.id, label: `${'  '.repeat(depth)}${resourceRootLabel.value}/${node.id}` })
            }
            result.push(...flattenFolders(node.children, depth + 1))
        }
        return result
    }

    const moveDestinations = computed(() => {
        const source = moveEntry.value
        return flattenFolders(treeData.value).map(folder => ({
            ...folder,
            disabled: source?.entryType === 'directory'
                && (folder.id === source.path || folder.id.startsWith(`${source.path}/`))
        }))
    })

    const fetchTree = async (preserveCurrentPath = false) => {
        try {
            if (isVNext.value) {
                const result = await vnextApi.assets(props.workspaceIdentity)
                vnextAssets = Array.isArray(result.assets) ? result.assets : []
                const makeFolderChildren = (category, folders) => {
                    const root = { name: category, id: category, type: 'directory', children: [], protected: true }
                    for (const folder of folders || []) {
                        let parent = root
                        let current = category
                        for (const part of String(folder).split('/').filter(Boolean)) {
                            current = `${current}/${part}`
                            let child = parent.children.find(item => item.id === current)
                            if (!child) { child = { name: part, id: current, type: 'directory', children: [] }; parent.children.push(child) }
                            parent = child
                        }
                    }
                    return root
                }
                treeData.value = MANAGED_ROOT_NAMES.map(rootName => {
                    const category = result.categories?.find(item => item.id === rootName)
                    return makeFolderChildren(rootName, category?.folders || [])
                })
                currentRelPath.value = preserveCurrentPath ? currentRelPath.value : (props.initialPath || 'image')
                await nextTick()
                treeRef.value?.setCurrentKey?.(currentRelPath.value)
                await fetchImages(currentRelPath.value)
                return
            }
            const res = await visionApi.getTemplatesTree(props.projectPath)
            const rawTree = Array.isArray(res.tree) ? res.tree : []
            // 同时容忍历史接口偶尔返回的虚拟根包装，但界面不再渲染这个
            // 异步根节点。三个用途目录必须是永久可见的顶层选项。
            const sourceChildren = rawTree.length === 1
                && !rawTree[0]?.id
                && Array.isArray(rawTree[0]?.children)
                ? rawTree[0].children
                : rawTree
            const managedRoots = MANAGED_ROOT_NAMES.map(rootName => {
                const existing = sourceChildren.find(item =>
                    String(item.id || item.name || '').replace(/\\/g, '/').split('/')[0].toLowerCase() === rootName)
                return existing
                    ? { ...existing, protected: true }
                    : { name: rootName, id: rootName, type: 'directory', children: [], protected: true }
            })
            const otherRoots = sourceChildren.filter(item => {
                const rootName = String(item.id || item.name || '').replace(/\\/g, '/').split('/')[0].toLowerCase()
                return !MANAGED_ROOT_NAMES.includes(rootName)
            })
            // 三个用途根目录直接作为顶层项，始终可见且顺序固定；initialPath
            // 只决定默认选中，绝不限制用户切换到其他用途目录。
            treeData.value = [...managedRoots, ...otherRoots]
            currentRelPath.value = preserveCurrentPath ? currentRelPath.value : (props.initialPath || '')
            await nextTick()
            treeRef.value?.setCurrentKey?.(currentRelPath.value)
            fetchImages(currentRelPath.value)
        } catch (err) {
            console.error('获取目录树失败', err)
            treeData.value = createManagedRoots()
            currentRelPath.value = preserveCurrentPath
                ? (currentRelPath.value || props.initialPath || 'image')
                : (props.initialPath || 'image')
            selectedImage.value = ''
            selectedAsset.value = null
            revokePreviewUrls()
            imageList.value = []
            await nextTick()
            treeRef.value?.setCurrentKey?.(currentRelPath.value)
            ElMessage.error(`资源目录加载失败：${err?.message || '请退出捕获后重试'}`)
        }
    }

    const revokePreviewUrls = () => {
        for (const image of imageList.value) {
            if (String(image.data || '').startsWith('blob:')) URL.revokeObjectURL(image.data)
        }
    }

    const loadImageBatch = async (generation, start, end) => {
        const targets = imageList.value.slice(start, end)
        const loaded = new Array(targets.length)
        let cursor = 0
        const loadOne = async image => {
            if (image.data) return image
            try {
                const blob = isVNext.value
                    ? await vnextApi.assetContent(props.workspaceIdentity, image.asset_id)
                    : await visionApi.getImageThumb(props.projectPath, image.asset_ref || image.relative_path)
                return { ...image, data: URL.createObjectURL(blob) }
            } catch {
                return image
            }
        }
        // 捕获保存先让目录和名称输入可用；缩略图用有界并发补齐，避免
        // 资源较多时一次打出 80 个内容请求并挤占确认事务。
        const worker = async () => {
            while (cursor < targets.length) {
                const index = cursor++
                loaded[index] = await loadOne(targets[index])
            }
        }
        await Promise.all(Array.from({ length: Math.min(6, targets.length) }, worker))
        if (generation !== previewGeneration) {
            loaded.forEach(image => image.data && URL.revokeObjectURL(image.data))
            return
        }
        const next = [...imageList.value]
        loaded.forEach((image, offset) => { next[start + offset] = image })
        imageList.value = next
    }

    const fetchImages = async (relPath) => {
        const generation = ++previewGeneration
        try {
            if (isVNext.value) {
                const [category, ...folderParts] = String(relPath || 'image').replace(/\\/g, '/').split('/').filter(Boolean)
                const folder = folderParts.join('/')
                revokePreviewUrls()
                imageList.value = vnextAssets.filter(asset => asset.category === category && String(asset.folder || '') === folder).map(asset => ({
                    ...asset, name: asset.display_name, relative_path: asset.path, asset_ref: `asset://${asset.asset_id}`, data: '',
                }))
                const batchSize = previewBatchSize()
                renderedImageCount.value = batchSize
                await loadImageBatch(generation, 0, Math.min(batchSize, imageList.value.length))
                return
            }
            const res = await visionApi.getTemplatePreview(props.projectPath, relPath)
            if (generation !== previewGeneration) return
            revokePreviewUrls()
            imageList.value = (res.images || []).map(image => ({ ...image, data: '' }))
            const batchSize = previewBatchSize()
            renderedImageCount.value = batchSize
            await loadImageBatch(generation, 0, Math.min(batchSize, imageList.value.length))
        } catch (err) {
            console.error('获取图片预览失败', err)
        }
    }

    const handleImageGridScroll = event => {
        const target = event.currentTarget
        if (!target || target.scrollHeight - target.scrollTop - target.clientHeight > 180) return
        const previous = renderedImageCount.value
        const next = Math.min(imageList.value.length, previous + previewBatchSize())
        if (next <= previous) return
        renderedImageCount.value = next
        loadImageBatch(previewGeneration, previous, next)
    }

    const formatBytes = (value) => {
        const bytes = Number(value || 0)
        if (bytes < 1024) return `${bytes} B`
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
        if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`
        return `${(bytes / 1024 / 1024 / 1024).toFixed(1)} GB`
    }

    const formatTrashTime = value => value ? new Date(value).toLocaleString() : '未知时间'

    const loadTrash = async () => {
        trashLoading.value = true
        try {
            const result = await visionApi.listTemplateTrash(props.projectPath)
            trashEntries.value = result.entries || []
            trashRetentionDays.value = result.retention_days || 30
            trashMaxBytes.value = result.max_bytes || 0
        } catch (error) {
            ElMessage.error(error.message || '读取资源回收站失败')
        } finally {
            trashLoading.value = false
        }
    }

    const openTrashDialog = async () => {
        trashDialogVisible.value = true
        await loadTrash()
    }

    const restoreTrashEntry = async entry => {
        if (!entry?.restorable || restoringTrashId.value) return
        restoringTrashId.value = entry.transaction_id
        try {
            await flushProjectBeforeMutation()
            const result = await visionApi.restoreTemplateEntry(props.projectPath, entry.transaction_id)
            notifyMutation('complete', 'restore', result)
            emit('mutated', result)
            await Promise.all([loadTrash(), fetchTree(true)])
            ElMessage.success('资源与捕获元数据已恢复；节点引用保持为空，请按需重新选择')
        } catch (error) {
            ElMessage.error(error.message || '恢复资源失败')
            await loadTrash()
        } finally {
            restoringTrashId.value = ''
        }
    }

    const handleFolderClick = (data) => {
        if (data.isCreating) return
        currentRelPath.value = data.id || ''
        selectedImage.value = ''
        selectedAsset.value = null
        fetchImages(currentRelPath.value)
    }

    const handleImageClick = (image) => {
        const cleanName = image.name.replace(/\.(png|jpg|jpeg)$/i, '')
        selectedImage.value = image.name
        selectedAsset.value = image
        if (isSaveMode.value) {
            saveFileName.value = cleanName
        }
    }

    const handleImageDblClick = (image) => {
        const cleanName = image.name.replace(/\.(png|jpg|jpeg)$/i, '')
        selectedImage.value = image.name
        selectedAsset.value = image
        if (isSaveMode.value) {
            saveFileName.value = cleanName
            handleSaveCheck()
        } else {
            confirmSelect()
        }
    }

    const handleImageKeyboard = (image) => {
        const alreadySelected = selectedImage.value === image.name
        handleImageClick(image)
        if (alreadySelected) {
            if (isSaveMode.value) handleSaveCheck()
            else confirmSelect()
        }
    }

    const handleFolderCommand = (command, data) => {
        if (command === 'move') openMoveDialog(data, 'directory')
        if (command === 'delete') confirmDelete(data.id)
    }

    const openMoveDialog = (entry, entryType) => {
        const path = entryType === 'directory' ? entry.id : entry.relative_path
        const parts = path.split('/')
        moveEntry.value = { path, entryType, assetId: entry.asset_id || '' }
        moveName.value = parts.pop() || ''
        moveTargetParent.value = parts.join('/') || props.initialPath || 'image'
        moveDialogVisible.value = true
    }

    const notifyMutation = (phase, operation, details = {}) => {
        publishResourceMutation({
            phase,
            operation,
            projectPath: props.projectPath,
            ...details
        })
    }

    const refreshAfterMutation = async (result) => {
        selectedImage.value = ''
        selectedAsset.value = null
        await fetchTree(true)
        notifyMutation('complete', result.operation, result)
        emit('mutated', result)
    }

    const impactMessage = (impact) => {
        const uniqueNodes = []
        const seen = new Set()
        for (const item of impact.references || []) {
            const key = `${item.canvas}:${item.task_id}:${item.node_id}`
            if (seen.has(key)) continue
            seen.add(key)
            uniqueNodes.push(item)
        }
        const children = [
            h('p', { class: 'impact-summary' }, `将删除 ${impact.file_count} 个文件、${impact.asset_count} 条资源记录。`)
        ]
        if (uniqueNodes.length) {
            children.push(h('p', { class: 'impact-warning' }, `有 ${uniqueNodes.length} 个节点正在使用这些图片；删除后图片值与录制坐标会自动清空：`))
            children.push(h('ul', { class: 'impact-node-list' }, uniqueNodes.slice(0, 8).map(item =>
                h('li', `${item.canvas === 'topology' ? '拓扑' : '流程'} / ${item.task_name || '未命名组'} / ${item.node_name || item.node_id}`)
            )))
            if (uniqueNodes.length > 8) children.push(h('p', `另有 ${uniqueNodes.length - 8} 个节点未展开显示。`))
        } else {
            children.push(h('p', { class: 'impact-safe' }, '当前没有节点引用此资源。'))
        }
        children.push(h('p', { class: 'impact-recovery' }, '文件会移入项目资源回收区，可人工恢复；默认分类目录不会被删除。'))
        return h('div', { class: 'resource-impact-message' }, children)
    }

    const confirmDelete = async (relativePath) => {
        if (!relativePath || mutationPending.value) return
        mutationPending.value = true
        try {
            if (isVNext.value) {
                if (!props.workspaceIdentity) throw new Error('vNext 工作区身份已失效')
                const asset = vnextAssets.find(item => item.path === relativePath || item.asset_id === relativePath)
                if (asset) {
                    const impact = await vnextApi.assetReferences(props.workspaceIdentity, asset.asset_id)
                    if (impact.references?.length) {
                        const referenceCount = impact.references.length
                        return ElMessage.warning(`该资源仍有 ${referenceCount} 处源码引用，请先替换或清除引用`)
                    }
                    await ElMessageBox.confirm('确认删除这项未被引用的资源？删除后无法从项目内恢复。', '确认删除图片', { type: 'warning', appendTo: 'body' })
                    const confirmed = await vnextApi.deleteAsset(props.workspaceIdentity, asset.asset_id)
                    if (confirmed.blocked) return ElMessage.warning('资源在确认期间产生了新引用，删除已取消')
                } else {
                    const impact = await vnextApi.deleteAssetFolder(props.workspaceIdentity, relativePath)
                    if (impact.blocked) {
                        const referenceCount = (impact.references || []).length
                        return ElMessage.warning(`文件夹中的资源仍有 ${referenceCount} 处源码引用，请先替换或清除引用`)
                    }
                    if (impact.requires_confirmation) {
                        await ElMessageBox.confirm(`文件夹包含 ${impact.asset_count || 0} 项资源。继续将删除这些未被引用的资源。`, '确认删除文件夹', { type: 'warning', appendTo: 'body' })
                        const confirmed = await vnextApi.deleteAssetFolder(props.workspaceIdentity, relativePath, true)
                        if (confirmed.blocked) return ElMessage.warning('文件夹在确认期间产生了新引用，删除已取消')
                    }
                }
                if (currentRelPath.value === relativePath || currentRelPath.value.startsWith(`${relativePath}/`)) currentRelPath.value = relativePath.split('/').slice(0, -1).join('/') || 'image'
                await fetchTree(true)
                emit('mutated', { operation: 'delete', path: relativePath })
                return ElMessage.success('资源已删除')
            }
            const impact = await visionApi.getTemplateImpact(props.projectPath, relativePath)
            if (impact.protected) return ElMessage.warning('image、ocr、page 默认分类不能删除')
            try {
                await ElMessageBox.confirm(impactMessage(impact), '确认删除资源', {
                    confirmButtonText: impact.node_count ? `删除并清空 ${impact.node_count} 个节点` : '确认删除',
                    cancelButtonText: '取消',
                    type: 'warning',
                    customClass: 'resource-delete-confirm',
                    appendTo: 'body'
                })
            } catch {
                return
            }
            await flushProjectBeforeMutation()
            notifyMutation('before', 'delete', { path: relativePath })
            const result = await visionApi.deleteTemplateEntry(props.projectPath, relativePath)
            if (currentRelPath.value === relativePath || currentRelPath.value.startsWith(`${relativePath}/`)) {
                currentRelPath.value = relativePath.split('/').slice(0, -1).join('/')
            }
            await refreshAfterMutation(result)
            ElMessage.success(result.node_count
                ? `资源已删除，并清空 ${result.node_count} 个节点的图片与坐标`
                : '资源已移入项目回收区')
        } catch (error) {
            if (error === 'cancel' || error === 'close') return
            ElMessage.error(error.message || '删除资源失败')
        } finally {
            mutationPending.value = false
        }
    }

    const submitMove = async () => {
        if (!moveEntry.value || !moveTargetParent.value || !moveName.value.trim() || mutationPending.value) return
        mutationPending.value = true
        const sourcePath = moveEntry.value.path
        try {
            if (isVNext.value) {
                if (!props.workspaceIdentity) throw new Error('vNext 工作区身份已失效')
                if (moveEntry.value.entryType === 'directory') {
                    await vnextApi.moveAssetFolder(props.workspaceIdentity, sourcePath, moveTargetParent.value, moveName.value.trim())
                } else {
                    const [category, ...folderParts] = moveTargetParent.value.split('/').filter(Boolean)
                    const asset = vnextAssets.find(item => item.asset_id === moveEntry.value.assetId || item.path === sourcePath)
                    if (!asset || !['image', 'ocr', 'page'].includes(category)) throw new Error('资源或目标目录已变化')
                    const displayName = moveName.value.trim().replace(/\.(png|jpe?g|bmp|webp)$/i, '')
                    await vnextApi.updateAsset(props.workspaceIdentity, asset.asset_id, { category, folder: folderParts.join('/'), display_name: displayName })
                }
                moveDialogVisible.value = false
                await fetchTree(true)
                emit('mutated', { operation: 'move', path: sourcePath })
                return ElMessage.success('资源已移动，稳定资源 ID 与源码引用保持不变')
            }
            await flushProjectBeforeMutation()
            notifyMutation('before', 'move', { path: sourcePath })
            const result = await visionApi.moveTemplateEntry(
                props.projectPath,
                sourcePath,
                moveTargetParent.value,
                moveName.value.trim()
            )
            if (result.status === 'unchanged') {
                moveDialogVisible.value = false
                return ElMessage.info('资源位置和名称没有变化')
            }
            if (moveEntry.value.entryType === 'directory'
                && (currentRelPath.value === sourcePath || currentRelPath.value.startsWith(`${sourcePath}/`))) {
                currentRelPath.value = currentRelPath.value.replace(sourcePath, result.new_path)
            }
            moveDialogVisible.value = false
            await refreshAfterMutation(result)
            ElMessage.success(result.reference_count
                ? `资源已移动，${result.reference_count} 处稳定资源引用继续有效`
                : '资源已移动；稳定资源引用保持不变')
        } catch (error) {
            ElMessage.error(error.message || '移动资源失败')
        } finally {
            mutationPending.value = false
        }
    }

    const inlineCreateFolder = (parentPath) => {
        const findParentNode = (nodes, path) => {
            for (const n of nodes) {
                if (n.id === path) return n
                if (n.children) {
                    const found = findParentNode(n.children, path)
                    if (found) return found
                }
            }
            return null
        }

        const parentNode = findParentNode(treeData.value, parentPath)
        // 新建入口只会由真实目录触发；找不到父目录时安全退出，避免把
        // 临时节点误塞进任意一个用途根目录。
        if (!parentNode) return ElMessage.error('目标文件夹已变化，请刷新后重试')
        const targetChildren = parentNode.children = parentNode.children || []

        const baseName = 'New_Folder'
        let defaultName = baseName
        let count = 1
        while (targetChildren.some(child => child.name === defaultName)) {
            defaultName = `${baseName}_${count}`
            count++
        }

        const newNode = {
            name: defaultName,
            id: `temp_${Date.now()}`,
            parentPath,
            isCreating: true,
            creatingName: defaultName
        }

        targetChildren.push(newNode)

        nextTick(() => {
            if (inlineInputRef.value) {
                inlineInputRef.value.focus()
                inlineInputRef.value.select()
            }
        })
    }

    const submitInlineFolder = async (nodeData) => {
        if (!nodeData.isCreating) return
        const folderName = nodeData.creatingName ? nodeData.creatingName.trim() : ''

        if (!folderName) {
            cancelInlineFolder(nodeData)
            return
        }

        nodeData.isCreating = false

        try {
            if (isVNext.value) {
                if (!props.workspaceIdentity) throw new Error('vNext 工作区身份已失效')
                const [category, ...parentParts] = String(nodeData.parentPath || '').split('/').filter(Boolean)
                if (!['image', 'ocr', 'page'].includes(category)) throw new Error('资源分类已变化')
                await vnextApi.createAssetFolder(props.workspaceIdentity, category, [...parentParts, folderName].join('/'))
            } else {
                await visionApi.createTemplateFolder(props.projectPath, nodeData.parentPath, folderName)
            }
            ElMessage.success(`文件夹 [${folderName}] 创建成功`)
            await fetchTree(true)
        } catch (err) {
            ElMessage.error(err.message || '创建文件夹失败')
            cancelInlineFolder(nodeData)
        }
    }

    const cancelInlineFolder = (nodeData) => {
        if (!nodeData.isCreating) return
        const removeNode = (nodes) => {
            const idx = nodes.findIndex(n => n.id === nodeData.id)
            if (idx > -1) {
                nodes.splice(idx, 1)
                return true
            }
            for (const n of nodes) {
                if (n.children && removeNode(n.children)) return true
            }
            return false
        }
        removeNode(treeData.value)
    }

    const handleSaveCheck = async () => {
        if (savePending.value) return
        const rawName = saveFileName.value.trim().replace(/\.png$/i, '')
        if (!rawName && !props.allowEmptyName) return ElMessage.warning('请输入图片名称')

        // 捕获模式由统一的捕获资源事务处理重名、覆盖和批量编号，FileBrowser
        // 只负责目录与名称输入，避免这里再维护一套碰撞规则。
        if (isCaptureSaveMode.value) {
            saving.value = true
            emit('save', {
                relativePath: currentRelPath.value,
                fileName: rawName
            })
            return
        }

        const fullName = `${rawName.toLowerCase()}.png`
        const isExist = imageList.value.some(img => img.name.toLowerCase() === fullName)

        if (isExist) {
            try {
                await ElMessageBox.confirm(
                    `当前目录下已存在同名图片 [${rawName}.png]，继续保存将覆盖原图片。是否继续？`,
                    '文件覆盖警告',
                    {
                        confirmButtonText: '确定覆盖',
                        cancelButtonText: '取消',
                        type: 'warning',
                        customClass: 'high-zindex-messagebox',
                        appendTo: 'body'
                    }
                )
            } catch {
                return
            }
        }

        saving.value = true
        emit('save', {
            relativePath: currentRelPath.value,
            fileName: rawName
        })
    }

    const confirmSelect = async () => {
        if (!selectedImage.value || !selectedAsset.value) return ElMessage.warning('请选择一张图片')
        let reference = selectedAsset.value.asset_ref || ''
        if (!reference) {
            try {
                const relativePath = selectedAsset.value.relative_path || [currentRelPath.value, selectedImage.value].filter(Boolean).join('/')
                const initialKind = props.initialPath.split('/')[0]
                const currentKind = currentRelPath.value.split('/')[0]
                const kind = ['image', 'ocr', 'page'].includes(initialKind)
                    ? initialKind
                    : (['image', 'ocr', 'page'].includes(currentKind) ? currentKind : 'image')
                const registered = await visionApi.registerTemplate(props.projectPath, relativePath, kind)
                reference = registered.asset_ref
                selectedAsset.value = { ...selectedAsset.value, ...registered }
            } catch (error) {
                return ElMessage.error(error.message || '图片注册失败')
            }
        }
        emit('select', reference)
    }

    // ⚡ 增加对 initialPath 和 mode 的全量监听
    watch(
        () => [props.projectPath, props.initialPath, props.mode, props.workspaceKind, props.workspaceIdentity?.generation],
        ([newPath, newInitPath]) => {
            if (newPath) {
                selectedImage.value = ''
                selectedAsset.value = null
                saveFileName.value = ''
                currentRelPath.value = newInitPath || ''
                fetchTree()
            }
        },
        { immediate: true }
    )

    // 捕获保存由宿主执行真实的资源事务，按钮必须跟随真实请求状态，不能
    // 在固定延时后提前恢复。父级 busy 生效后即可释放本地点击锁；请求
    // 完成时 busy 变回 false，界面才重新允许提交。
    watch(
        () => props.saveBusy,
        busy => {
            if (busy) saving.value = false
        }
    )

    onBeforeUnmount(() => {
        previewGeneration++
        revokePreviewUrls()
    })

</script>

<style scoped>
    .file-browser.dark-theme {
        display: flex;
        height: 480px;
        background: var(--el-bg-color-page);
        color: var(--el-text-color-regular);
        border-radius: var(--app-radius-md, 8px);
        overflow: hidden;
        border: 1px solid var(--el-border-color-light);
    }

    .file-browser.is-fill-height {
        height: 100%;
        border: 0;
        border-radius: 0;
    }

    .tree-sidebar {
        width: 240px;
        background: var(--el-bg-color);
        border-right: 1px solid var(--el-border-color-light);
        display: flex;
        flex-direction: column;
    }

    .tree-header {
        padding: 10px 12px;
        font-size: 13px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        border-bottom: 1px solid var(--el-border-color-light);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .trash-button {
        color: var(--el-text-color-placeholder);
        font-size: 10px;
        font-weight: 500;
    }

    .trash-list {
        min-height: 120px;
        max-height: 420px;
        overflow-y: auto;
    }

    .trash-caption {
        margin-bottom: 12px;
        color: var(--el-text-color-secondary);
        font-size: 12px;
        line-height: 1.55;
    }

    .trash-entry {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        padding: 11px 0;
        border-bottom: 1px solid var(--el-border-color-lighter);
    }

    .trash-entry-main {
        min-width: 0;
    }

    .trash-path {
        overflow: hidden;
        color: var(--el-text-color-primary);
        font-size: 13px;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .trash-meta,
    .trash-empty {
        margin-top: 4px;
        color: var(--el-text-color-placeholder);
        font-size: 11px;
    }

    .trash-empty {
        padding: 44px 0;
        text-align: center;
    }

    .tree-wrapper {
        flex: 1;
        overflow-y: auto;
        padding: 6px;
    }

    :deep(.el-tree) {
        background: transparent;
        color: var(--el-text-color-regular);
    }

    .custom-tree-node {
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        padding-right: 6px;
        font-size: 12px;
    }

    .node-actions {
        display: inline-flex;
        align-items: center;
        gap: 2px;
        min-height: 24px;
    }

    .node-icon-btn {
        width: 24px;
        height: 24px;
        padding: 0;
        color: var(--el-text-color-secondary);
    }

    .node-icon-btn:hover {
        color: var(--el-color-primary);
    }

    .protected-icon {
        margin: 0 5px;
        color: var(--el-text-color-placeholder);
    }

    /* ⚡ 拓扑资产目录标记徽章 */
    .topo-badge {
        display: inline-block;
        background: var(--el-color-primary);
        color: #fff;
        font-size:10px;
        padding: 1px 5px;
        border-radius: 3px;
        margin-right: 4px;
        line-height: 1.3;
        vertical-align: middle;
    }

    .inline-folder-input {
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-color-primary);
        color: var(--el-text-color-primary);
        border-radius: 4px;
        padding: 1px 6px;
        font-size: 12px;
        width: 120px;
        outline: none;
    }

    .content-body {
        flex: 1;
        display: flex;
        flex-direction: column;
        background: var(--el-bg-color-page);
    }

    .location-bar {
        padding: 10px 16px;
        font-size: 12px;
        color: var(--el-text-color-secondary);
        border-bottom: 1px solid var(--el-border-color-light);
        background: var(--el-bg-color);
    }

    .path-highlight {
        color: var(--el-color-primary);
        font-weight: 600;
        margin-left: 4px;
    }

    .image-grid {
        flex: 1;
        padding: 12px;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
        gap: 12px;
        overflow-y: auto;
        align-content: start;
    }

    .image-card {
        border: 1px solid var(--el-border-color-light);
        border-radius: var(--app-radius-sm, 6px);
        padding: 6px;
        background: var(--el-bg-color);
        cursor: pointer;
        transition: border-color 0.16s ease, background-color 0.16s ease, box-shadow 0.16s ease;
        display: flex;
        flex-direction: column;
        align-items: center;
        user-select: none;
    }

        .image-card:hover {
            border-color: var(--el-color-primary);
            box-shadow: 0 0 0 1px color-mix(in srgb, var(--el-color-primary) 22%, transparent);
        }

        .image-card:focus-visible {
            outline: none;
            border-color: var(--el-color-primary);
            box-shadow: var(--focus-ring);
        }

        .image-card.selected {
            border-color: var(--el-color-primary);
    background: var(--app-color-primary-dim);
        }

    .img-wrapper {
        position: relative;
        width: 100%;
        height: 75px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--el-fill-color-blank);
        border-radius: 4px;
        overflow: hidden;
    }

    .image-actions {
        position: absolute;
        top: 5px;
        right: 5px;
        display: flex;
        gap: 4px;
        opacity: 0;
        transform: translateY(-3px);
        transition: opacity 0.15s ease, transform 0.15s ease;
    }

    .image-card:hover .image-actions,
    .image-card.selected .image-actions {
        opacity: 1;
        transform: translateY(0);
    }

    .image-actions :deep(.el-button) {
        width: 25px;
        height: 25px;
        margin-left: 0;
        border-color: color-mix(in srgb, var(--el-border-color) 70%, transparent);
        background: color-mix(in srgb, var(--el-bg-color-overlay) 90%, transparent);
        box-shadow: 0 3px 10px rgba(0, 0, 0, 0.28);
        backdrop-filter: blur(8px);
    }

        .img-wrapper img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }

    .image-name {
        font-size: 11px;
        color: var(--el-text-color-secondary);
        margin-top: 6px;
        text-align: center;
        width: 100%;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .empty-tip {
        grid-column: 1 / -1;
        color: var(--el-text-color-placeholder);
        font-size: 13px;
        text-align: center;
        margin-top: 60px;
    }

    .action-footer {
        padding: 12px 16px;
        background: var(--el-bg-color);
        border-top: 1px solid var(--el-border-color-light);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .input-group {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .btn-group {
        display: flex;
        gap: 8px;
        align-items: center;
    }

    .move-form {
        display: grid;
        gap: 9px;
    }

    .move-form label {
        margin-top: 4px;
        color: var(--el-text-color-secondary);
        font-size: 12px;
        font-weight: 600;
    }

    .move-source {
        padding: 9px 11px;
        overflow: hidden;
        border: 1px solid var(--el-border-color-light);
        border-radius: var(--app-radius-sm, 6px);
        background: var(--el-fill-color-light);
        color: var(--el-text-color-regular);
        font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
        font-size: 12px;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    :global(.resource-impact-message p) {
        margin: 0 0 10px;
        line-height: 1.55;
    }

    :global(.resource-impact-message .impact-warning) {
        color: var(--el-color-warning);
        font-weight: 600;
    }

    :global(.resource-impact-message .impact-node-list) {
        max-height: 160px;
        margin: 0 0 12px;
        padding: 8px 8px 8px 28px;
        overflow-y: auto;
        border-radius: 7px;
        background: var(--el-fill-color-light);
        color: var(--el-text-color-regular);
        font-size: 12px;
    }

    :global(.resource-impact-message .impact-safe) {
        color: var(--el-color-success);
    }

    :global(.resource-impact-message .impact-recovery) {
        color: var(--el-text-color-secondary);
        font-size: 12px;
    }
</style>
