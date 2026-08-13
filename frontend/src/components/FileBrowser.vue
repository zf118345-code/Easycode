<!-- frontend/src/components/FileBrowser.vue -->
<template>
    <div class="file-browser dark-theme">
        <!-- 左侧目录树区域 -->
        <div class="tree-sidebar">
            <div class="tree-header">
                <span>📁 文件夹目录</span>
                <el-button type="primary" link size="small" @click="inlineCreateFolder('')">
                    ➕ 根新建
                </el-button>
            </div>

            <!-- ⚡ 拓扑模式资产目录引导提示条 -->
            <div v-if="store.canvasMode === 'topology'" class="topology-asset-tip">
                <span class="tip-icon">🧭</span>
                <span class="tip-text">拓扑资产模式：已自动定位至 <strong>topology_assets/</strong> 目录</span>
            </div>

            <div class="tree-wrapper">
                <el-tree ref="treeRef"
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
                                <span class="node-icon">📁</span>
                                <input ref="inlineInputRef"
                                       v-model="data.creatingName"
                                       class="inline-folder-input"
                                       @keyup.enter="submitInlineFolder(data)"
                                       @keyup.esc="cancelInlineFolder(data)"
                                       @blur="submitInlineFolder(data)" />
                            </template>
                            <template v-else>
                                <span class="node-label">
                                    <span v-if="data.isTopologyRoot" class="topo-badge">拓扑</span>
                                    📁 {{ node.label }}
                                </span>
                                <el-button class="node-mkdir-btn"
                                           type="primary"
                                           link
                                           size="small"
                                           title="在此目录下新建子文件夹"
                                           @click.stop="inlineCreateFolder(data.id)">
                                    +
                                </el-button>
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
                <strong class="path-highlight">/{{ store.canvasMode === 'topology' ? 'topology_assets' : 'templates' }}/{{ currentRelPath || '(根目录)' }}</strong>
            </div>

            <!-- 图片网格查看 -->
            <div class="image-grid">
                <div v-for="img in imageList"
                     :key="img.name"
                     class="image-card"
                     :class="{ selected: selectedImage === img.name }"
                     @click="handleImageClick(img.name)"
                     @dblclick="handleImageDblClick(img.name)">
                    <div class="img-wrapper">
                        <img :src="img.data" :alt="img.name" />
                    </div>
                    <div class="image-name" :title="img.name">{{ img.name }}</div>
                </div>
                <div v-if="!imageList.length" class="empty-tip">
                    📂 当前目录下暂无图片，可在下方直接输入新名称保存
                </div>
            </div>

            <!-- 底部保存/选择操作栏 -->
            <div v-if="mode === 'save'" class="action-footer">
                <div class="input-group">
                    <span class="input-label">图片名称:</span>
                    <el-input v-model="saveFileName"
                              placeholder="点击图片复制名，或输入新名称"
                              clearable
                              style="width: 300px;"
                              @keyup.enter="handleSaveCheck" />
                </div>
                <div class="btn-group">
                    <el-button @click="$emit('close')">取消</el-button>
                    <el-button type="primary" :loading="saving" @click="handleSaveCheck">保存截图</el-button>
                </div>
            </div>

            <div v-else class="action-footer">
                <span class="tip-text">💡 单击填充名，双击直接确认选择</span>
                <div class="btn-group">
                    <el-button type="info" @click="$emit('close')">取消</el-button>
                    <el-button type="success" :disabled="!selectedImage" @click="confirmSelect">
                        确定选择
                    </el-button>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { ref, watch, nextTick } from 'vue'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import { visionApi } from '@/api/visionApi'
    import { useMainStore } from '@/stores'

    const props = defineProps({
        projectPath: { type: String, required: true },
        mode: { type: String, default: 'select' },
        initialPath: { type: String, default: '' }
    })

    const emit = defineEmits(['select', 'save', 'close'])

    const store = useMainStore()

    // ⚡ 拓扑模式专属资产目录名
    const TOPOLOGY_ASSET_DIR = 'topology_assets'

    const treeRef = ref(null)
    const inlineInputRef = ref(null)

    const treeData = ref([])
    const imageList = ref([])
    const currentRelPath = ref('')
    const selectedImage = ref('')
    const saveFileName = ref('')
    const saving = ref(false)

    const defaultProps = { children: 'children', label: 'name' }

    // ⚡ 拓扑模式下需要确保 topology_assets 目录存在，并在树中标记为拓扑根目录
    const ensureTopologyAssetDir = async () => {
        if (!props.projectPath) return
        try {
            // 复用 createTemplateFolder 创建 topology_assets 目录（已存在则安全忽略）
            await visionApi.createTemplateFolder(props.projectPath, '', TOPOLOGY_ASSET_DIR)
        } catch {
            /* 已存在则安全忽略 */
        }
    }

    // ⚡ 将目录树中的 topology_assets 节点标记为拓扑根目录
    const markTopologyRootInTree = (nodes) => {
        const walk = (list) => {
            for (const n of list) {
                if (n.name === TOPOLOGY_ASSET_DIR) {
                    n.isTopologyRoot = true
                }
                if (n.children && n.children.length) walk(n.children)
            }
        }
        walk(nodes)
    }

    const fetchTree = async () => {
        try {
            // ⚡ 拓扑模式下先确保资产目录存在，并将 initialPath 指向 topology_assets
            if (store.canvasMode === 'topology') {
                await ensureTopologyAssetDir()
                if (!props.initialPath) {
                    currentRelPath.value = TOPOLOGY_ASSET_DIR
                }
            }

            if (props.initialPath) {
                try {
                    await visionApi.createTemplateFolder(props.projectPath, '', props.initialPath)
                } catch {
                    /* 已存在则安全忽略 */
                }
            }

            const res = await visionApi.getTemplatesTree(props.projectPath)
            const children = res.tree || []
            // ⚡ 拓扑模式下标记拓扑资产目录节点
            if (store.canvasMode === 'topology') {
                markTopologyRootInTree(children)
            }
            treeData.value = [
                { name: '根目录 (templates)', id: '', children }
            ]

            // ⚡ 拓扑模式下自动导航到 topology_assets 目录
            if (store.canvasMode === 'topology') {
                currentRelPath.value = TOPOLOGY_ASSET_DIR
            } else {
                currentRelPath.value = props.initialPath || ''
            }
            fetchImages(currentRelPath.value)
        } catch (err) {
            console.error('获取目录树失败', err)
        }
    }

    const fetchImages = async (relPath) => {
        try {
            const res = await visionApi.getTemplatePreview(props.projectPath, relPath)
            imageList.value = res.images || []
        } catch (err) {
            console.error('获取图片预览失败', err)
        }
    }

    const handleFolderClick = (data) => {
        if (data.isCreating) return
        currentRelPath.value = data.id || ''
        selectedImage.value = ''
        fetchImages(currentRelPath.value)
    }

    const handleImageClick = (fileName) => {
        const cleanName = fileName.replace(/\.png$/i, '')
        selectedImage.value = fileName
        if (props.mode === 'save') {
            saveFileName.value = cleanName
        }
    }

    const handleImageDblClick = (fileName) => {
        const cleanName = fileName.replace(/\.png$/i, '')
        selectedImage.value = fileName
        if (props.mode === 'save') {
            saveFileName.value = cleanName
            handleSaveCheck()
        } else {
            confirmSelect()
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
        const targetChildren = parentNode ? (parentNode.children = parentNode.children || []) : treeData.value[0].children

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
            await visionApi.createTemplateFolder(props.projectPath, nodeData.parentPath, folderName)
            ElMessage.success(`文件夹 [${folderName}] 创建成功`)
            await fetchTree()
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
        const rawName = saveFileName.value.trim().replace(/\.png$/i, '')
        if (!rawName) return ElMessage.warning('请输入图片名称')

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
        setTimeout(() => { saving.value = false }, 500)
    }

    const confirmSelect = () => {
        if (!selectedImage.value) return ElMessage.warning('请选择一张图片')
        const cleanImgName = selectedImage.value.replace(/\.png$/i, '')
        const fullPath = currentRelPath.value
            ? `${currentRelPath.value}/${cleanImgName}`
            : cleanImgName
        emit('select', fullPath)
    }

    // ⚡ 增加对 initialPath 和 mode 的全量监听
    watch(
        () => [props.projectPath, props.initialPath, props.mode],
        ([newPath, newInitPath]) => {
            if (newPath) {
                selectedImage.value = ''
                saveFileName.value = ''
                currentRelPath.value = newInitPath || ''
                fetchTree()
            }
        },
        { immediate: true }
    )

    // ⚡ 监听画布模式切换：进入拓扑模式时自动导航到 topology_assets 资产目录
    watch(
        () => store.canvasMode,
        (newMode) => {
            if (newMode === 'topology' && props.projectPath) {
                currentRelPath.value = TOPOLOGY_ASSET_DIR
                fetchTree()
                ElMessage.info('已切换到拓扑资产目录 topology_assets/')
            } else if (newMode === 'workflow' && props.projectPath) {
                currentRelPath.value = props.initialPath || ''
                fetchTree()
            }
        }
    )
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

    /* ⚡ 拓扑模式资产目录引导提示条 */
    .topology-asset-tip {
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        background: rgba(78, 209, 156, 0.1);
        border-bottom: 1px solid rgba(78, 209, 156, 0.25);
        font-size: 11px;
        color: var(--el-color-primary);
    }

    .tip-icon {
        font-size: 13px;
        flex-shrink: 0;
    }

    .topology-asset-tip .tip-text {
        line-height: 1.4;
    }

        .topology-asset-tip .tip-text strong {
            color: var(--el-color-primary);
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

    /* ⚡ 拓扑资产目录标记徽章 */
    .topo-badge {
        display: inline-block;
        background: var(--el-color-primary);
        color: #fff;
        font-size: 9px;
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
        transition: all 0.2s;
        display: flex;
        flex-direction: column;
        align-items: center;
        user-select: none;
    }

        .image-card:hover {
            border-color: var(--el-color-primary);
            transform: translateY(-2px);
        }

        .image-card.selected {
            border-color: var(--el-color-primary);
            background: rgba(78, 209, 156, 0.15);
        }

    .img-wrapper {
        width: 100%;
        height: 75px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--el-fill-color-blank);
        border-radius: 4px;
        overflow: hidden;
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
</style>
