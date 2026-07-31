<template>
  <div class="file-browser">
    <div class="browser-container">
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
            <img :src="img.data" :alt="img.name" />
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
import axios from 'axios'
import { Folder } from '@element-plus/icons-vue'

export default {
  name: 'FileBrowser',
  components: { Folder },
  props: {
    modelValue: { type: String, default: '' },
    projectPath: { type: String, default: '' }
  },
  emits: ['update:modelValue', 'select', 'close'],
  setup(props, { emit }) {
    const store = useMainStore()
    const loading = ref(false)
    const treeData = ref([])
    const treeProps = { children: 'children', label: 'name' }
    const currentPath = ref('/')
    const currentRelativePath = ref('')
    const images = ref([])
    const selectedImage = ref('')

    const loadTree = async () => {
      const path = props.projectPath || store.currentProjectPath
      if (!path) {
        ElMessage.warning('请先打开项目')
        return
      }
      loading.value = true
      try {
        const res = await axios.get('/api/templates/tree', {
          params: { project_path: path }
        })
        treeData.value = [{
          name: 'templates',
          id: '',
          children: res.data.tree || []
        }]
        currentPath.value = '/'
        currentRelativePath.value = ''
        await loadPreview('')
      } catch (err) {
        ElMessage.error('加载目录失败')
        console.error(err)
      } finally {
        loading.value = false
      }
    }

    const loadPreview = async (relativePath) => {
      const path = props.projectPath || store.currentProjectPath
      if (!path) return
      try {
        const res = await axios.get('/api/templates/preview', {
          params: {
            project_path: path,
            relative_path: relativePath
          }
        })
        images.value = res.data.images || []
      } catch (err) {
        console.error('加载预览失败', err)
        images.value = []
      }
    }

    const onNodeClick = async (data, node) => {
      const relPath = data.id || ''
      currentRelativePath.value = relPath
      currentPath.value = relPath ? `/${relPath}` : '/'
      await loadPreview(relPath)
      selectedImage.value = ''
    }

    const selectImage = (img) => {
      selectedImage.value = img.name
    }

    const confirmSelection = () => {
      if (selectedImage.value) {
        const baseName = selectedImage.value.replace('.png', '')
        const relPath = currentRelativePath.value
        const fullPath = relPath ? `${relPath}/${baseName}` : baseName
        emit('update:modelValue', fullPath)
        emit('select', fullPath)
        closeDialog()
      }
    }

    const refreshTree = () => {
      loadTree()
    }

    const closeDialog = () => {
      emit('close')
    }

    // 监听项目路径变化
    watch(() => props.projectPath, () => {
      loadTree()
    })

    onMounted(() => {
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
.tree-body .loading {
  color: #8a8fa8;
  text-align: center;
  padding: 20px;
}
.tree-body .el-tree {
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