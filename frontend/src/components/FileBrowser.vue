<template>
  <div class="file-browser">
    <div class="browser-container">
      <!-- 左侧目录树 -->
      <div class="tree-wrapper">
        <div class="tree-header">
          <span>📁 模板目录</span>
          <el-button size="small" type="primary" @click="refreshTree">刷新</el-button>
        </div>
        <div v-if="loading" class="loading">加载中...</div>
        <el-tree
          v-else
          :data="treeData"
          :props="treeProps"
          default-expand-all
          highlight-current
          @node-click="onNodeClick"
          node-key="id"
          :expand-on-click-node="false"
        >
          <template #default="{ node, data }">
            <span class="tree-node">
              <el-icon><Folder /></el-icon>
              <span>{{ node.label }}</span>
            </span>
          </template>
        </el-tree>
      </div>

      <!-- 右侧预览 -->
      <div class="preview-wrapper">
        <div class="preview-header">
          <span>📷 图片预览</span>
          <span v-if="currentPath" class="path">{{ currentPath }}</span>
        </div>
        <div class="preview-grid" v-if="images.length">
          <div
            v-for="img in images"
            :key="img.name"
            class="preview-item"
            :class="{ selected: selectedImage === img.name }"
            @click="selectImage(img)"
            @dblclick="confirmSelection"
          >
            <img :src="img.url" :alt="img.name" />
            <div class="preview-name">{{ img.name }}</div>
          </div>
        </div>
        <div v-else class="empty-preview">该目录下暂无图片</div>
      </div>
    </div>

    <div class="browser-footer">
      <span v-if="selectedImage" class="selected-info">已选: {{ selectedImage }}</span>
      <div>
        <el-button @click="closeDialog">取消</el-button>
        <el-button type="primary" :disabled="!selectedImage" @click="confirmSelection">选择</el-button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, watch } from 'vue'
import { useMainStore } from '@/stores'
import { ElMessage } from 'element-plus'
import { Folder } from '@element-plus/icons-vue'

export default {
  name: 'FileBrowser',
  components: { Folder },
  props: {
    modelValue: {
      type: String,
      default: ''
    }
  },
  emits: ['update:modelValue', 'select', 'close'],
  setup(props, { emit }) {
    const store = useMainStore()
    const loading = ref(false)
    const treeData = ref([])
    const treeProps = { children: 'children', label: 'name' }
    const currentPath = ref('')
    const images = ref([])
    const selectedImage = ref('')
    const currentDirHandle = ref(null)
    const templatesHandle = ref(null)

    const loadTree = async () => {
      if (!store.workspaceHandle || !store.currentProject) {
        ElMessage.warning('请先设置工作区并选择项目')
        return
      }
      loading.value = true
      try {
        const projectHandle = await store.workspaceHandle.getDirectoryHandle(store.currentProject)
        let templates
        try {
          templates = await projectHandle.getDirectoryHandle('templates')
        } catch {
          templates = await projectHandle.getDirectoryHandle('templates', { create: true })
        }
        templatesHandle.value = templates
        currentDirHandle.value = templates
        currentPath.value = '/'
        // 构建树
        const rootNode = await buildTree(templates, '')
        rootNode.name = 'templates'
        rootNode.id = ''
        treeData.value = [rootNode]
        // 加载根目录图片
        await loadImages(templates)
      } catch (err) {
        console.error('加载目录失败', err)
        ElMessage.error('加载目录失败')
      } finally {
        loading.value = false
      }
    }

    const buildTree = async (dirHandle, relativePath) => {
      const node = {
        name: dirHandle.name || '根目录',
        id: relativePath || '',
        children: []
      }
      for await (const [name, handle] of dirHandle.entries()) {
        if (handle.kind === 'directory') {
          const childPath = relativePath ? `${relativePath}/${name}` : name
          const childNode = await buildTree(handle, childPath)
          childNode.name = name
          childNode.id = childPath
          node.children.push(childNode)
        }
      }
      node.children.sort((a, b) => a.name.localeCompare(b.name))
      return node
    }

    const loadImages = async (dirHandle) => {
      images.value = []
      try {
        for await (const [name, handle] of dirHandle.entries()) {
          if (handle.kind === 'file' && name.toLowerCase().endsWith('.png')) {
            const file = await handle.getFile()
            const url = URL.createObjectURL(file)
            images.value.push({ name, url, handle })
          }
        }
        images.value.sort((a, b) => a.name.localeCompare(b.name))
      } catch (err) {
        console.warn('加载预览失败:', err)
      }
    }

    const onNodeClick = async (data) => {
      try {
        let targetHandle = templatesHandle.value
        if (data.id !== '') {
          const pathParts = data.id.split('/').filter(Boolean)
          for (const part of pathParts) {
            targetHandle = await targetHandle.getDirectoryHandle(part)
          }
        }
        currentDirHandle.value = targetHandle
        currentPath.value = data.id === '' ? '/' : `/${data.id}`
        await loadImages(targetHandle)
        selectedImage.value = ''
      } catch (err) {
        ElMessage.error('切换目录失败')
      }
    }

    const selectImage = (img) => {
      selectedImage.value = img.name
    }

    const confirmSelection = () => {
      if (selectedImage.value) {
        const baseName = selectedImage.value.replace('.png', '')
        let fullPath = currentPath.value === '/' ? '' : currentPath.value.slice(1)
        const relPath = fullPath ? `${fullPath}/${baseName}` : baseName
        emit('update:modelValue', relPath)
        emit('select', relPath)
        closeDialog()
      }
    }

    const refreshTree = () => {
      loadTree()
    }

    const closeDialog = () => {
      emit('close')
    }

    // 清理 object URLs
    const revokeUrls = () => {
      images.value.forEach(img => URL.revokeObjectURL(img.url))
    }

    onMounted(() => {
      loadTree()
    })

    watch(() => store.currentProject, () => {
      loadTree()
    })

    return {
      loading,
      treeData,
      treeProps,
      currentPath,
      images,
      selectedImage,
      onNodeClick,
      selectImage,
      confirmSelection,
      refreshTree,
      closeDialog
    }
  }
}
</script>

<style scoped>
.file-browser {
  display: flex;
  flex-direction: column;
  height: 60vh;
}
.browser-container {
  display: flex;
  flex: 1;
  gap: 16px;
  overflow: hidden;
}
.tree-wrapper {
  flex: 1;
  border: 1px solid #3d3d5a;
  border-radius: 4px;
  background: #1a1a2e;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #2d2d44;
  border-bottom: 1px solid #3d3d5a;
  flex-shrink: 0;
  color: #cfd3e6;
}
.tree-header .el-button {
  padding: 2px 8px;
}
.tree-wrapper .loading {
  color: #8a8fa8;
  text-align: center;
  padding: 20px;
}
.tree-wrapper .el-tree {
  flex: 1;
  overflow: auto;
  background: transparent;
  color: #cfd3e6;
}
.tree-node {
  display: flex;
  align-items: center;
  gap: 4px;
}
.tree-node .el-icon {
  font-size: 18px;
}
.preview-wrapper {
  flex: 2;
  border: 1px solid #3d3d5a;
  border-radius: 4px;
  background: #1a1a2e;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #2d2d44;
  border-bottom: 1px solid #3d3d5a;
  flex-shrink: 0;
  color: #cfd3e6;
}
.preview-header .path {
  font-size: 12px;
  color: #8a8fa8;
}
.preview-grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(80px, 1fr));
  gap: 8px;
  padding: 8px;
}
.preview-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  background: #282a3a;
  border-radius: 4px;
  padding: 4px;
  cursor: pointer;
  transition: background 0.2s;
  border: 2px solid transparent;
}
.preview-item:hover {
  background: #3d3d5a;
}
.preview-item.selected {
  border-color: #409EFF;
  background: #4a4a6a;
}
.preview-item img {
  width: 64px;
  height: 64px;
  object-fit: contain;
  border-radius: 2px;
}
.preview-name {
  font-size: 11px;
  color: #8a8fa8;
  text-align: center;
  word-break: break-all;
  max-width: 70px;
}
.empty-preview {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8a8fa8;
}
.browser-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-top: 1px solid #3d3d5a;
  background: #2d2d44;
  flex-shrink: 0;
}
.selected-info {
  color: #cfd3e6;
  font-size: 13px;
}
</style>