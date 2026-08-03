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
                            <!-- 如果是正在创建的内联输入节点 -->
                            <template v-if="data.isCreating">
                                <span class="node-icon">📁</span>
                                <input ref="inlineInputRef"
                                       v-model="data.creatingName"
                                       class="inline-folder-input"
                                       @keyup.enter="submitInlineFolder(data)"
                                       @keyup.esc="cancelInlineFolder(data)"
                                       @blur="submitInlineFolder(data)" />
                            </template>

                            <!-- 普通文件夹节点 -->
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

<script>
    import { ref, watch, nextTick } from 'vue'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import axios from 'axios'

    export default {
        name: 'FileBrowser',
        props: {
            projectPath: { type: String, required: true },
            mode: { type: String, default: 'select' } // 'select' | 'save'
        },
        emits: ['select', 'save', 'close'],
        setup(props, { emit }) {
            const treeRef = ref(null)
            const inlineInputRef = ref(null)

            const treeData = ref([])
            const imageList = ref([])
            const currentRelPath = ref('')
            const selectedImage = ref('')
            const saveFileName = ref('')
            const saving = ref(false)

            const defaultProps = { children: 'children', label: 'name' }

            // 拉取目录树
            const fetchTree = async () => {
                try {
                    const res = await axios.get('/api/templates/tree', {
                        params: { project_path: props.projectPath }
                    })
                    treeData.value = [
                        { name: '根目录 (templates)', id: '', children: res.data.tree || [] }
                    ]
                } catch (err) {
                    console.error('获取目录树失败', err)
                }
            }

            // 拉取图片预览
            const fetchImages = async (relPath) => {
                try {
                    const res = await axios.get('/api/templates/preview', {
                        params: { project_path: props.projectPath, relative_path: relPath }
                    })
                    imageList.value = res.data.images || []
                } catch (err) {
                    console.error('获取图片预览失败', err)
                }
            }

            // 选中文件夹
            const handleFolderClick = (data) => {
                if (data.isCreating) return
                currentRelPath.value = data.id || ''
                selectedImage.value = ''
                fetchImages(currentRelPath.value)
            }

            // ⭐ 单击图片：自动清洗并去除 .png 后缀填充给输入框
            const handleImageClick = (fileName) => {
                const cleanName = fileName.replace(/\.png$/i, '')
                selectedImage.value = fileName
                if (props.mode === 'save') {
                    saveFileName.value = cleanName
                }
            }

            // ⭐ 双击图片：自动清洗并直接提交或选择
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

            // 内联插入新文件夹
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

                let baseName = 'New_Folder'
                let defaultName = baseName
                let count = 1
                while (targetChildren.some(child => child.name === defaultName)) {
                    defaultName = `${baseName}_${count}`
                    count++
                }

                const newNode = {
                    name: defaultName,
                    id: `temp_${Date.now()}`,
                    parentPath: parentPath,
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

            // 提交创建内联文件夹
            const submitInlineFolder = async (nodeData) => {
                if (!nodeData.isCreating) return
                const folderName = nodeData.creatingName ? nodeData.creatingName.trim() : ''

                if (!folderName) {
                    cancelInlineFolder(nodeData)
                    return
                }

                nodeData.isCreating = false

                try {
                    await axios.post('/api/templates/mkdir', {
                        project_path: props.projectPath,
                        parent_path: nodeData.parentPath,
                        folder_name: folderName
                    })
                    ElMessage.success(`文件夹 [${folderName}] 创建成功`)
                    await fetchTree()
                } catch (err) {
                    ElMessage.error(err.response?.data?.detail || '创建文件夹失败')
                    cancelInlineFolder(nodeData)
                }
            }

            // 取消内联新建
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

            // ⭐ 保存校验与重名弹窗（包含强制 z-index 提升）
            const handleSaveCheck = async () => {
                // 深度清洗后缀
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
                                customClass: 'high-zindex-messagebox', // ⭐ 对应最高层级提示
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
                    fileName: rawName // ⭐ 回传彻底纯净的不含 .png 的名称
                })
                setTimeout(() => { saving.value = false }, 500)
            }

            const confirmSelect = () => {
                if (!selectedImage.value) return ElMessage.warning('请选择一张图片')
                // 选择已存在的图片时，自动剥离 .png 确保填回输入框的是干净路径
                const cleanImgName = selectedImage.value.replace(/\.png$/i, '')
                const fullPath = currentRelPath.value
                    ? `${currentRelPath.value}/${cleanImgName}`
                    : cleanImgName
                emit('select', fullPath)
            }

            watch(
                () => props.projectPath,
                () => {
                    if (props.projectPath) {
                        fetchTree()
                        fetchImages('')
                    }
                },
                { immediate: true }
            )

            return {
                treeRef,
                inlineInputRef,
                treeData,
                imageList,
                currentRelPath,
                selectedImage,
                saveFileName,
                saving,
                defaultProps,
                handleFolderClick,
                handleImageClick,
                handleImageDblClick,
                inlineCreateFolder,
                submitInlineFolder,
                cancelInlineFolder,
                handleSaveCheck,
                confirmSelect
            }
        }
    }
</script>

<style scoped>
    .file-browser.dark-theme {
        display: flex;
        height: 480px;
        background: var(--el-bg-color-page);
        color: var(--el-text-color-regular);
        border-radius: 8px;
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
        border-radius: 6px;
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