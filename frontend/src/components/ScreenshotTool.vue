<template>
  <el-dialog
    v-model="visible"
    title="截图工具"
    width="95%"
    top="5vh"
    :close-on-click-modal="false"
    append-to-body
    @close="close"
  >
    <div class="screenshot-container">
      <!-- 左侧截图区 -->
      <div class="canvas-wrapper" v-if="imgLoaded">
        <canvas
          ref="canvas"
          @mousedown="onMouseDown"
          @mousemove="onMouseMove"
          @mouseup="onMouseUp"
          @mouseleave="onMouseUp"
        ></canvas>
      </div>
      <div class="canvas-wrapper" v-else style="display:flex;align-items:center;justify-content:center;color:#8a8fa8;">
        加载截图中...
      </div>

      <!-- 右侧预览 + 微调 -->
      <div class="preview-wrapper">
        <div class="preview-header">
          <span>🔍 框选放大预览</span>
        </div>
        <div class="preview-canvas-wrapper">
          <canvas ref="previewCanvas"></canvas>
        </div>
        <div class="preview-info">
          <span>框选区域: {{ selectionRect ? `${Math.round(selectionRect.w)}x${Math.round(selectionRect.h)}` : '未框选' }}</span>
        </div>
        <div class="adjust-area" v-if="imgLoaded">
          <div class="adjust-row">
            <label>X:</label>
            <el-input-number v-model="adjustX" :min="0" :max="Math.max(0, imgWidth - 1)" size="small" controls-position="right" @change="applyAdjust" />
            <label>Y:</label>
            <el-input-number v-model="adjustY" :min="0" :max="Math.max(0, imgHeight - 1)" size="small" controls-position="right" @change="applyAdjust" />
          </div>
          <div class="adjust-row">
            <label>W:</label>
            <el-input-number v-model="adjustW" :min="1" :max="Math.max(1, imgWidth - adjustX)" size="small" controls-position="right" @change="applyAdjust" />
            <label>H:</label>
            <el-input-number v-model="adjustH" :min="1" :max="Math.max(1, imgHeight - adjustY)" size="small" controls-position="right" @change="applyAdjust" />
          </div>
        </div>
        <div class="action-buttons">
          <el-button type="primary" size="small" @click="showSaveDialog" :disabled="!selectionRect">💾 保存图片</el-button>
          <el-button size="small" @click="clearSelection">清除框选</el-button>
        </div>
      </div>
    </div>

    <!-- 保存图片对话框 -->
    <el-dialog
      title="保存图片"
      v-model="saveDialogVisible"
      width="70%"
      append-to-body
      :close-on-click-modal="false"
      @open="initSaveDialog"
    >
      <div class="save-container">
        <div class="tree-wrapper">
          <div class="tree-header">
            <el-button size="small" type="primary" @click="createNewFolder">📁 新建文件夹</el-button>
            <span class="current-path">当前路径: {{ currentPath || '/' }}</span>
          </div>
          <div class="tree-body">
            <div v-if="treeLoading" class="loading">加载目录树...</div>
            <el-tree
              v-else
              ref="treeRef"
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
        </div>

        <div class="preview-area">
          <div class="preview-header-right">
            <span>📷 图片预览</span>
            <span v-if="previewImages.length" class="count">{{ previewImages.length }} 张</span>
          </div>
          <div class="preview-grid" v-if="previewImages.length">
            <div
              v-for="(img, idx) in previewImages"
              :key="idx"
              class="preview-item"
              @click="selectExistingTemplate(img)"
            >
              <img :src="img.data" :alt="img.name" />
              <div class="preview-name">{{ img.name }}</div>
            </div>
          </div>
          <div v-else class="empty-preview">该目录下暂无图片</div>
        </div>
      </div>
      <div class="save-footer">
        <el-form label-width="80px">
          <el-form-item label="文件名">
            <el-input v-model="saveFileName" placeholder="请输入图片名称（不含扩展名）" />
          </el-form-item>
        </el-form>
        <div>
          <el-button @click="saveDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmSaveTemplate">保存</el-button>
        </div>
      </div>
    </el-dialog>
  </el-dialog>
</template>

<script>
import { ref, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { useMainStore } from '@/stores'
import { Folder } from '@element-plus/icons-vue'

export default {
  name: 'ScreenshotTool',
  components: { Folder },
  setup() {
    const store = useMainStore()
    const visible = ref(false)
    const saveDialogVisible = ref(false)
    const canvas = ref(null)
    const previewCanvas = ref(null)

    // 截图相关状态
    const img = ref(null)
    const imgLoaded = ref(false)
    const imgWidth = ref(0)
    const imgHeight = ref(0)
    const selectionRect = ref(null)
    const isDragging = ref(false)
    const startX = ref(0)
    const startY = ref(0)
    const adjustX = ref(0)
    const adjustY = ref(0)
    const adjustW = ref(0)
    const adjustH = ref(0)

    // 目录树相关状态
    const treeData = ref([])
    const treeRef = ref(null)
    const treeProps = { children: 'children', label: 'name' }
    const currentPath = ref('/')
    const currentRelativePath = ref('')
    const saveFileName = ref('')
    const previewImages = ref([])
    const treeLoading = ref(false)

    // 绘图上下文变量（修复关键）
    let canvasCtx = null
    let previewCtx = null

    // ====== 截图功能 ======
    const open = async () => {
      visible.value = true
      await nextTick()
      await captureScreen()
    }

    const close = () => {
      visible.value = false
      saveDialogVisible.value = false
    }

    const captureScreen = async () => {
      imgLoaded.value = false
      const context = store.currentContext
      const payload = {
        window_title: context.windowTitle || '',
        offset_top: context.offsetTop || 0,
        offset_bottom: context.offsetBottom || 0,
        offset_left: context.offsetLeft || 0,
        offset_right: context.offsetRight || 0,
        is_emulator: context.isEmulator || false
      }
      try {
        const res = await axios.post('/api/screenshot', payload)
        const base64 = res.data.image
        const image = new Image()
        image.onload = () => {
          img.value = image
          imgWidth.value = image.width
          imgHeight.value = image.height
          imgLoaded.value = true
          resetSelection()
          clearPreview()
          nextTick(() => drawCanvas())
        }
        image.src = base64
      } catch (err) {
        ElMessage.error('截图失败: ' + err.message)
        imgLoaded.value = false
      }
    }

    const resetSelection = () => {
      adjustX.value = 0
      adjustY.value = 0
      adjustW.value = 0
      adjustH.value = 0
      selectionRect.value = null
    }

    const drawCanvas = () => {
      if (!canvas.value || !img.value) return
      const c = canvas.value
      const rect = c.parentElement.getBoundingClientRect()
      const containerWidth = rect.width
      const containerHeight = rect.height
      const ratio = Math.min(containerWidth / imgWidth.value, containerHeight / imgHeight.value)
      const displayWidth = imgWidth.value * ratio
      const displayHeight = imgHeight.value * ratio
      const offsetX = (containerWidth - displayWidth) / 2
      const offsetY = (containerHeight - displayHeight) / 2
      c.width = containerWidth
      c.height = containerHeight
      canvasCtx = c.getContext('2d')
      canvasCtx.clearRect(0, 0, containerWidth, containerHeight)
      canvasCtx.drawImage(img.value, offsetX, offsetY, displayWidth, displayHeight)
      c._scale = ratio
      c._offsetX = offsetX
      c._offsetY = offsetY
      if (selectionRect.value) {
        drawSelection()
      }
    }

    const drawSelection = () => {
      if (!canvasCtx || !selectionRect.value) return
      const c = canvas.value
      const scale = c._scale || 1
      const offX = c._offsetX || 0
      const offY = c._offsetY || 0
      const { x, y, w, h } = selectionRect.value
      canvasCtx.strokeStyle = 'red'
      canvasCtx.lineWidth = 2
      canvasCtx.strokeRect(offX + x * scale, offY + y * scale, w * scale, h * scale)
      updatePreview()
    }

    const updatePreview = () => {
      if (!previewCanvas.value || !selectionRect.value) return
      const pv = previewCanvas.value
      const rect = pv.parentElement.getBoundingClientRect()
      const containerWidth = rect.width
      const containerHeight = rect.height
      const { x, y, w, h } = selectionRect.value
      if (w === 0 || h === 0) { clearPreview(); return }
      const cropCanvas = document.createElement('canvas')
      cropCanvas.width = w
      cropCanvas.height = h
      const cropCtx = cropCanvas.getContext('2d')
      cropCtx.drawImage(img.value, x, y, w, h, 0, 0, w, h)
      const ratio = Math.min(containerWidth / w, containerHeight / h)
      const displayW = w * ratio
      const displayH = h * ratio
      const offX = (containerWidth - displayW) / 2
      const offY = (containerHeight - displayH) / 2
      pv.width = containerWidth
      pv.height = containerHeight
      previewCtx = pv.getContext('2d')
      previewCtx.clearRect(0, 0, containerWidth, containerHeight)
      previewCtx.drawImage(cropCanvas, offX, offY, displayW, displayH)
    }

    const clearPreview = () => {
      if (previewCanvas.value) {
        const pv = previewCanvas.value
        const ctx = pv.getContext('2d')
        ctx.clearRect(0, 0, pv.width, pv.height)
      }
    }

    // 鼠标事件
    const onMouseDown = (e) => {
      if (!canvas.value || !imgLoaded.value) return
      const rect = canvas.value.getBoundingClientRect()
      const scale = canvas.value._scale || 1
      const offX = canvas.value._offsetX || 0
      const offY = canvas.value._offsetY || 0
      const x = (e.clientX - rect.left - offX) / scale
      const y = (e.clientY - rect.top - offY) / scale
      if (x < 0 || y < 0 || x > imgWidth.value || y > imgHeight.value) return
      isDragging.value = true
      startX.value = x
      startY.value = y
      selectionRect.value = { x, y, w: 0, h: 0 }
    }

    const onMouseMove = (e) => {
      if (!isDragging.value || !canvas.value || !imgLoaded.value) return
      const rect = canvas.value.getBoundingClientRect()
      const scale = canvas.value._scale || 1
      const offX = canvas.value._offsetX || 0
      const offY = canvas.value._offsetY || 0
      const x = (e.clientX - rect.left - offX) / scale
      const y = (e.clientY - rect.top - offY) / scale
      const sx = Math.min(startX.value, x)
      const sy = Math.min(startY.value, y)
      const ex = Math.max(startX.value, x)
      const ey = Math.max(startY.value, y)
      selectionRect.value = {
        x: Math.round(Math.max(0, sx)),
        y: Math.round(Math.max(0, sy)),
        w: Math.round(Math.min(ex, imgWidth.value) - Math.max(0, sx)),
        h: Math.round(Math.min(ey, imgHeight.value) - Math.max(0, sy))
      }
      adjustX.value = selectionRect.value.x
      adjustY.value = selectionRect.value.y
      adjustW.value = selectionRect.value.w
      adjustH.value = selectionRect.value.h
      drawCanvas()
    }

    const onMouseUp = () => {
      if (isDragging.value) {
        isDragging.value = false
        if (selectionRect.value && (selectionRect.value.w < 2 || selectionRect.value.h < 2)) {
          resetSelection()
          drawCanvas()
          clearPreview()
        } else {
          updatePreview()
        }
      }
    }

    const applyAdjust = () => {
      if (!imgLoaded.value) return
      const x = Math.round(adjustX.value)
      const y = Math.round(adjustY.value)
      const w = Math.round(adjustW.value)
      const h = Math.round(adjustH.value)
      if (x < 0 || y < 0 || w <= 0 || h <= 0 || x + w > imgWidth.value || y + h > imgHeight.value) {
        ElMessage.warning('无效的框选区域')
        return
      }
      selectionRect.value = { x, y, w, h }
      drawCanvas()
      updatePreview()
    }

    const clearSelection = () => {
      resetSelection()
      drawCanvas()
      clearPreview()
    }

    // ====== 保存对话框相关（后端驱动） ======
    const showSaveDialog = () => {
      if (!selectionRect.value) {
        ElMessage.warning('请先框选一个区域')
        return
      }
      if (!store.currentProjectPath) {
        ElMessage.warning('请先打开项目')
        return
      }
      saveDialogVisible.value = true
    }

    const initSaveDialog = async () => {
      treeLoading.value = true
      try {
        await loadTree()
        await loadPreview('')
        saveFileName.value = ''
      } catch (err) {
        ElMessage.error('加载目录失败: ' + err.message)
      } finally {
        treeLoading.value = false
      }
    }

    const loadTree = async () => {
      if (!store.currentProjectPath) {
        ElMessage.warning('请先打开项目')
        return
      }
      try {
        const res = await axios.get('/api/templates/tree', {
          params: { project_path: store.currentProjectPath }
        })
        treeData.value = [{
          name: 'templates',
          id: '',
          children: res.data.tree || []
        }]
        currentPath.value = '/'
        currentRelativePath.value = ''
      } catch (err) {
        console.error('加载目录树失败', err)
        ElMessage.error('加载目录树失败')
      }
    }

    const loadPreview = async (relativePath) => {
      if (!store.currentProjectPath) return
      try {
        const res = await axios.get('/api/templates/preview', {
          params: {
            project_path: store.currentProjectPath,
            relative_path: relativePath
          }
        })
        previewImages.value = res.data.images || []
      } catch (err) {
        console.error('加载预览失败', err)
        previewImages.value = []
      }
    }

    const onNodeClick = async (data, node) => {
      const relPath = data.id || ''
      currentRelativePath.value = relPath
      currentPath.value = relPath ? `/${relPath}` : '/'
      await loadPreview(relPath)
    }

    const createNewFolder = async () => {
      if (!store.currentProjectPath) {
        ElMessage.warning('请先打开项目')
        return
      }
      try {
        const { value: folderName } = await ElMessageBox.prompt('请输入新文件夹名称', '新建文件夹', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          inputPattern: /^[^\/:*?"<>|]+$/,
          inputErrorMessage: '文件夹名称不合法'
        })
        if (folderName) {
          await axios.post('/api/templates/mkdir', {
            project_path: store.currentProjectPath,
            relative_path: currentRelativePath.value,
            dir_name: folderName
          })
          ElMessage.success('文件夹创建成功')
          await loadTree()
          await loadPreview(currentRelativePath.value)
        }
      } catch (err) {
        if (err !== 'cancel') {
          ElMessage.error('创建失败: ' + err.message)
        }
      }
    }

    const selectExistingTemplate = (img) => {
      const baseName = img.name.replace('.png', '')
      saveFileName.value = baseName
      ElMessage.info(`已填充文件名: ${baseName}`)
    }

    const confirmSaveTemplate = async () => {
      if (!selectionRect.value) {
        ElMessage.warning('请先框选一个区域')
        return
      }
      const name = saveFileName.value.trim()
      if (!name) {
        ElMessage.warning('请输入文件名')
        return
      }
      if (!store.currentProjectPath) {
        ElMessage.warning('请先打开项目')
        return
      }

      const { x, y, w, h } = selectionRect.value
      const region = [Math.round(x), Math.round(y), Math.round(w), Math.round(h)]
      const cropCanvas = document.createElement('canvas')
      cropCanvas.width = w
      cropCanvas.height = h
      const cropCtx = cropCanvas.getContext('2d')
      cropCtx.drawImage(img.value, x, y, w, h, 0, 0, w, h)
      const blob = await new Promise(resolve => cropCanvas.toBlob(resolve, 'image/png'))

      const subdir = currentRelativePath.value
      const fileName = `${name}.png`

      try {
        const formData = new FormData()
        formData.append('project_path', store.currentProjectPath)
        formData.append('template_name', name)
        formData.append('subdir', subdir)
        formData.append('region_x', region[0])
        formData.append('region_y', region[1])
        formData.append('region_w', region[2])
        formData.append('region_h', region[3])
        formData.append('image', blob, fileName)

        await axios.post('/api/screenshot/save', formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        ElMessage.success(`图片已保存 (${subdir ? subdir + '/' : ''}${name})`)
        saveDialogVisible.value = false
        // 刷新预览
        await loadPreview(currentRelativePath.value)
        // 刷新目录树
        await loadTree()
      } catch (err) {
        ElMessage.error('保存失败: ' + (err.response?.data?.detail || err.message))
      }
    }

    const onResize = () => {
      if (visible.value && imgLoaded.value) {
        drawCanvas()
        if (selectionRect.value) updatePreview()
      }
    }

    onMounted(() => {
      window.addEventListener('resize', onResize)
    })

    onBeforeUnmount(() => {
      window.removeEventListener('resize', onResize)
    })

    return {
      visible,
      saveDialogVisible,
      canvas,
      previewCanvas,
      imgLoaded,
      imgWidth,
      imgHeight,
      selectionRect,
      adjustX,
      adjustY,
      adjustW,
      adjustH,
      treeData,
      treeRef,
      treeProps,
      currentPath,
      saveFileName,
      previewImages,
      treeLoading,
      open,
      close,
      onMouseDown,
      onMouseMove,
      onMouseUp,
      applyAdjust,
      clearSelection,
      showSaveDialog,
      initSaveDialog,
      onNodeClick,
      createNewFolder,
      selectExistingTemplate,
      confirmSaveTemplate,
      captureScreen,
      drawCanvas,
      updatePreview
    }
  }
}
</script>

<style scoped>
/* 所有样式保持不变，参考你之前已有的样式 */
.screenshot-container {
  display: flex;
  height: 65vh;
  gap: 16px;
}
.canvas-wrapper {
  flex: 2;
  background: #1a1a2e;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}
.canvas-wrapper canvas {
  width: 100%;
  height: 100%;
  display: block;
  cursor: crosshair;
}
.preview-wrapper {
  flex: 1;
  background: #282a3a;
  border-radius: 6px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.preview-header {
  color: #cfd3e6;
  font-weight: 500;
}
.preview-canvas-wrapper {
  flex: 2;
  background: #1a1a2e;
  border-radius: 4px;
  overflow: hidden;
}
.preview-canvas-wrapper canvas {
  width: 100%;
  height: 100%;
  display: block;
}
.preview-info {
  color: #8a8fa8;
  font-size: 12px;
}
.adjust-area {
  display: flex;
  flex-direction: column;
  gap: 4px;
  background: #32324a;
  padding: 8px;
  border-radius: 4px;
}
.adjust-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.adjust-row label {
  color: #cfd3e6;
  font-size: 12px;
  width: 16px;
}
.adjust-row .el-input-number {
  width: 70px;
}
.action-buttons {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
.save-container {
  display: flex;
  height: 50vh;
  gap: 16px;
}
.tree-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid #3d3d5a;
  border-radius: 4px;
  background: #1a1a2e;
  overflow: hidden;
}
.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #2d2d44;
  border-bottom: 1px solid #3d3d5a;
  flex-shrink: 0;
}
.current-path {
  color: #8a8fa8;
  font-size: 12px;
  margin-left: 12px;
}
.tree-body {
  flex: 1;
  overflow: auto;
  padding: 8px;
}
.tree-body .loading {
  color: #8a8fa8;
  text-align: center;
  padding: 20px;
}
.tree-node {
  display: flex;
  align-items: center;
  gap: 4px;
  color: #cfd3e6;
}
.tree-node .el-icon {
  font-size: 18px;
}
.preview-area {
  flex: 1.5;
  display: flex;
  flex-direction: column;
  border: 1px solid #3d3d5a;
  border-radius: 4px;
  background: #1a1a2e;
  overflow: hidden;
}
.preview-header-right {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #2d2d44;
  border-bottom: 1px solid #3d3d5a;
  flex-shrink: 0;
  color: #cfd3e6;
}
.preview-header-right .count {
  font-size: 12px;
  color: #8a8fa8;
}
.preview-grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
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
}
.preview-item img {
  width: 80px;
  height: 80px;
  object-fit: contain;
  border-radius: 2px;
}
.preview-name {
  font-size: 11px;
  color: #8a8fa8;
  text-align: center;
  word-break: break-all;
  max-width: 80px;
}
.empty-preview {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #8a8fa8;
}
.save-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #3d3d5a;
}
.save-footer .el-form {
  flex: 1;
}
.save-footer .el-form-item {
  margin-bottom: 0;
}
</style>