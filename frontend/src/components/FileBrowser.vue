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
                                <span class="node-label">📁 {{ node.label }}</span>
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
                <strong class="path-highlight">/templates/{{ currentRelPath || '(根目录)' }}</strong>
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

    const props = defineProps({
        projectPath: { type: String, required: true },
        mode: { type: String, default: 'select' },
        initialPath: { type: String, default: '' }
    })

    const emit = defineEmits(['select', 'save', 'close'])

    const treeRef = ref(null)
    const inlineInputRef = ref(null)

    const treeData = ref([])
    const imageList = ref([])
    const currentRelPath = ref('')
    const selectedImage = ref('')
    const saveFileName = ref('')
    const saving = ref(false)

    const defaultProps = { children: 'children', label: 'name' }

    const fetchTree = async () => {
        try {
            if (props.initialPath) {
                try {
                    await visionApi.createTemplateFolder(props.projectPath, '', props.initialPath)
                } catch {
                    /* 已存在则安全忽略 */
                }
            }

            const res = await visionApi.getTemplatesTree(props.projectPath)
            treeData.value = [
                { name: '根目录 (templates)', id: '', children: res.tree || [] }
            ]

            currentRelPath.value = props.initialPath || ''
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