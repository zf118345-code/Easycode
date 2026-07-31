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
        <el-select
          v-model="localContext.windowTitle"
          filterable
          placeholder="选择或输入窗口标题"
          @focus="fetchWindows"
        >
          <el-option
            v-for="w in windowList"
            :key="w.hwnd"
            :label="w.title"
            :value="w.title"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="模拟器模式">
        <el-switch v-model="localContext.isEmulator" />
      </el-form-item>
      <el-form-item label="裁剪 (T,B,L,R)">
        <el-input-number v-model="localContext.offsetTop" :min="0" controls-position="right" style="width:80px;" />
        <el-input-number v-model="localContext.offsetBottom" :min="0" controls-position="right" style="width:80px;" />
        <el-input-number v-model="localContext.offsetLeft" :min="0" controls-position="right" style="width:80px;" />
        <el-input-number v-model="localContext.offsetRight" :min="0" controls-position="right" style="width:80px;" />
      </el-form-item>
      <el-form-item label="目标内容尺寸">
        <el-input-number v-model="localContext.targetContentWidth" :min="0" placeholder="宽" style="width:100px;" />
        <span style="margin:0 4px;">×</span>
        <el-input-number v-model="localContext.targetContentHeight" :min="0" placeholder="高" style="width:100px;" />
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
  emits: ['update:visible', 'apply'],
  setup(props, { emit }) {
    const store = useMainStore()
    const localContext = ref({
      windowTitle: store.currentContext.windowTitle || '',
      isEmulator: store.currentContext.isEmulator || false,
      offsetTop: store.currentContext.offsetTop || 0,
      offsetBottom: store.currentContext.offsetBottom || 0,
      offsetLeft: store.currentContext.offsetLeft || 0,
      offsetRight: store.currentContext.offsetRight || 0,
      targetContentWidth: store.currentContext.targetContentWidth || 0,
      targetContentHeight: store.currentContext.targetContentHeight || 0
    })
    const windowList = ref([])

    const dialogVisible = computed({
      get: () => props.visible,
      set: (val) => emit('update:visible', val)
    })

    watch(() => props.visible, (val) => {
      if (val) {
        localContext.value = {
          windowTitle: store.currentContext.windowTitle || '',
          isEmulator: store.currentContext.isEmulator || false,
          offsetTop: store.currentContext.offsetTop || 0,
          offsetBottom: store.currentContext.offsetBottom || 0,
          offsetLeft: store.currentContext.offsetLeft || 0,
          offsetRight: store.currentContext.offsetRight || 0,
          targetContentWidth: store.currentContext.targetContentWidth || 0,
          targetContentHeight: store.currentContext.targetContentHeight || 0
        }
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
      emit('apply', localContext.value)
      dialogVisible.value = false
    }

    const onClose = () => { dialogVisible.value = false }

    return { localContext, dialogVisible, windowList, applyContext, onClose, fetchWindows }
  }
}
</script>