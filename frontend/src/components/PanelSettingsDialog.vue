<template>
  <el-dialog
    title="工作面板设置"
    v-model="dialogVisible"
    width="500px"
    append-to-body
    :close-on-click-modal="false"
    @close="onClose"
  >
    <el-form :model="localContext" label-width="100px" size="small">
      <el-form-item label="窗口标题">
        <el-select v-model="localContext.windowTitle" filterable placeholder="选择或输入窗口标题" @focus="fetchWindows">
          <el-option v-for="w in windowList" :key="w.hwnd" :label="w.title" :value="w.title" />
        </el-select>
      </el-form-item>
      <el-form-item label="模拟器模式">
        <el-switch v-model="localContext.isEmulator" />
      </el-form-item>
      <template v-if="localContext.isEmulator">
        <el-form-item label="设备 ID">
          <el-input v-model="localContext.deviceId" placeholder="如 127.0.0.1:5555" />
        </el-form-item>
        <el-form-item label="分辨率">
          <el-input-number v-model="localContext.androidWidth" :min="0" controls-position="right" style="width:100px;" />
          <span style="margin:0 8px;">x</span>
          <el-input-number v-model="localContext.androidHeight" :min="0" controls-position="right" style="width:100px;" />
        </el-form-item>
      </template>
      <el-form-item label="裁剪 (T,B,L,R)">
        <el-input-number v-model="localContext.offsetTop" :min="0" controls-position="right" style="width:80px;" />
        <el-input-number v-model="localContext.offsetBottom" :min="0" controls-position="right" style="width:80px;" />
        <el-input-number v-model="localContext.offsetLeft" :min="0" controls-position="right" style="width:80px;" />
        <el-input-number v-model="localContext.offsetRight" :min="0" controls-position="right" style="width:80px;" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="dialogVisible = false">取消</el-button>
      <el-button type="primary" @click="applyContext">应用</el-button>
    </template>
  </el-dialog>
</template>

<script>
import { useMainStore } from '@/stores'
import { ref, watch, computed } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

export default {
  name: 'PanelSettingsDialog',
  props: { visible: { type: Boolean, default: false } },
  emits: ['update:visible'],
  setup(props, { emit }) {
    const store = useMainStore()
    const localContext = ref({ ...store.currentContext })
    const windowList = ref([])

    const dialogVisible = computed({
      get: () => props.visible,
      set: (val) => emit('update:visible', val)
    })

    watch(() => props.visible, (val) => {
      if (val) {
        localContext.value = { ...store.currentContext }
        fetchWindows()
      }
    })

    const fetchWindows = async () => {
      try {
        const res = await axios.get('/api/windows')
        windowList.value = res.data.windows || []
      } catch (err) {
        console.error('获取窗口列表失败', err)
      }
    }

    const applyContext = () => {
      store.setCurrentContext(localContext.value)
      ElMessage.success('工作面板已更新')
      dialogVisible.value = false
    }

    const onClose = () => { dialogVisible.value = false }

    return { localContext, dialogVisible, windowList, applyContext, onClose, fetchWindows }
  }
}
</script>