<template>
  <div class="param-renderer">
    <!-- 标签 -->
    <div v-if="label" class="param-label">{{ label }}</div>

    <!-- 控件 -->
    <div class="param-control">
      <!-- str -->
      <template v-if="config.type === 'str'">
        <el-input
          v-model="localValue"
          :placeholder="config.label || ''"
          @change="emitChange"
        />
      </template>

      <!-- int -->
      <template v-else-if="config.type === 'int'">
        <el-input-number
          v-model="localValue"
          :min="config.min !== undefined ? config.min : 0"
          :max="config.max !== undefined ? config.max : Infinity"
          :step="config.step || 1"
          controls-position="right"
          @change="emitChange"
        />
      </template>

      <!-- float -->
      <template v-else-if="config.type === 'float'">
        <el-input-number
          v-model="localValue"
          :min="config.min !== undefined ? config.min : 0"
          :max="config.max !== undefined ? config.max : Infinity"
          :step="config.step || 0.1"
          :precision="2"
          controls-position="right"
          @change="emitChange"
        />
      </template>

      <!-- bool -->
      <template v-else-if="config.type === 'bool'">
        <el-switch
          v-model="localValue"
          @change="emitChange"
        />
      </template>

      <!-- select -->
      <template v-else-if="config.type === 'select'">
        <el-select
          v-model="localValue"
          :placeholder="config.label || '请选择'"
          @change="emitChange"
        >
          <el-option
            v-for="opt in resolvedOptions"
            :key="opt"
            :label="opt"
            :value="opt"
          />
        </el-select>
      </template>

      <!-- file -->
      <template v-else-if="config.type === 'file'">
        <div class="file-selector">
          <el-input
            :model-value="localValue"
            placeholder="请选择模板图片"
            readonly
            @click="openFileDialog"
          >
            <template #append>
              <el-button @click="openFileDialog">📂 浏览</el-button>
            </template>
          </el-input>
          <el-button type="success" size="small" @click="openScreenshot">📷 录入</el-button>
        </div>
      </template>

      <!-- list_int2 -->
      <template v-else-if="config.type === 'list_int2'">
        <div class="list-int2">
          <div class="coord-item">
            <span class="coord-label">X</span>
            <el-input-number
              v-model="localValue[0]"
              :min="0"
              controls-position="right"
              size="small"
              @change="emitChange"
            />
          </div>
          <div class="coord-item">
            <span class="coord-label">Y</span>
            <el-input-number
              v-model="localValue[1]"
              :min="0"
              controls-position="right"
              size="small"
              @change="emitChange"
            />
          </div>
        </div>
      </template>

      <!-- list_int4 -->
      <template v-else-if="config.type === 'list_int4'">
        <div class="list-int4">
          <div class="coord-item">
            <span class="coord-label">X</span>
            <el-input-number
              v-model="localValue[0]"
              :min="0"
              controls-position="right"
              size="small"
              @change="emitChange"
            />
          </div>
          <div class="coord-item">
            <span class="coord-label">Y</span>
            <el-input-number
              v-model="localValue[1]"
              :min="0"
              controls-position="right"
              size="small"
              @change="emitChange"
            />
          </div>
          <div class="coord-item">
            <span class="coord-label">W</span>
            <el-input-number
              v-model="localValue[2]"
              :min="0"
              controls-position="right"
              size="small"
              @change="emitChange"
            />
          </div>
          <div class="coord-item">
            <span class="coord-label">H</span>
            <el-input-number
              v-model="localValue[3]"
              :min="0"
              controls-position="right"
              size="small"
              @change="emitChange"
            />
          </div>
        </div>
      </template>

      <!-- list_dict -->
      <template v-else-if="config.type === 'list_dict'">
        <div class="list-dict">
          <el-table
            :data="localValue"
            border
            size="small"
            style="width: 100%"
          >
            <el-table-column
              v-for="(subConfig, subKey) in config.sub"
              :key="subKey"
              :label="subConfig.label || subKey"
              :prop="subKey"
              min-width="120"
            >
              <template #default="{ row }">
                <ParamRenderer
                  :config="subConfig"
                  :value="row[subKey]"
                  @update="(val) => { row[subKey] = val; emitChange(); }"
                />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="80">
              <template #default="{ $index }">
                <el-button
                  type="danger"
                  size="small"
                  link
                  @click="removeListItem($index)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-table-column>
            <template #append>
              <el-button size="small" @click="addListItem">
                <el-icon><Plus /></el-icon> 添加
              </el-button>
            </template>
          </el-table>
        </div>
      </template>

      <!-- dict -->
      <template v-else-if="config.type === 'dict'">
        <div class="dict-container">
          <ParamRenderer
            v-for="(subConfig, subKey) in config.sub"
            :key="subKey"
            :config="subConfig"
            :value="localValue[subKey]"
            :label="subConfig.label || subKey"
            @update="(val) => { localValue[subKey] = val; emitChange(); }"
          />
        </div>
      </template>

      <!-- 未知类型 -->
      <template v-else>
        <el-tag type="warning">未知类型: {{ config.type }}</el-tag>
      </template>
    </div>

    <!-- 文件浏览器对话框 -->
    <el-dialog
      v-model="browserVisible"
      title="选择模板图片"
      width="80%"
      top="5vh"
      append-to-body
      :close-on-click-modal="false"
      @close="browserVisible = false"
    >
      <FileBrowser
        ref="fileBrowserRef"
        @select="onFileSelected"
        @close="browserVisible = false"
      />
    </el-dialog>

    <!-- 截图工具 -->
    <ScreenshotTool ref="screenshotTool" @saved="onScreenshotSaved" />
  </div>
</template>

<script>
import { ref, watch, onBeforeUnmount, computed } from 'vue'
import { Delete, Plus } from '@element-plus/icons-vue'
import ScreenshotTool from '@/components/ScreenshotTool.vue'
import FileBrowser from '@/components/FileBrowser.vue'

export default {
  name: 'ParamRenderer',
  components: { Delete, Plus, ScreenshotTool, FileBrowser },
  props: {
    config: {
      type: Object,
      required: true
    },
    value: {
      required: false
    },
    label: {
      type: String,
      default: ''
    },
    context: {
      type: Object,
      default: () => ({})
    }
  },
  emits: ['update', 'openScreenshot'],
  setup(props, { emit }) {
    const getInitialValue = () => {
      const val = props.value
      if (props.config.type === 'list_int4') {
        return Array.isArray(val) && val.length === 4 ? val : [0, 0, 0, 0]
      } else if (props.config.type === 'list_int2') {
        return Array.isArray(val) && val.length === 2 ? val : [0, 0]
      } else if (props.config.type === 'list_dict') {
        return Array.isArray(val) ? val : []
      }
      return val
    }

    const localValue = ref(getInitialValue())
    const screenshotTool = ref(null)
    const browserVisible = ref(false)
    const fileBrowserRef = ref(null)

    // 计算 options（支持函数）
    const resolvedOptions = computed(() => {
      const options = props.config.options
      if (typeof options === 'function') {
        try {
          return options(props.context, localValue.value) || []
        } catch (e) {
          console.warn('options 函数执行出错', e)
          return []
        }
      }
      return Array.isArray(options) ? options : []
    })

    // 监听外部 value
    const unwatch = watch(
      () => props.value,
      (newVal) => {
        let fixedVal = newVal
        if (props.config.type === 'list_int4') {
          fixedVal = Array.isArray(newVal) && newVal.length === 4 ? newVal : [0, 0, 0, 0]
        } else if (props.config.type === 'list_int2') {
          fixedVal = Array.isArray(newVal) && newVal.length === 2 ? newVal : [0, 0]
        } else if (props.config.type === 'list_dict') {
          fixedVal = Array.isArray(newVal) ? newVal : []
        }
        if (JSON.stringify(fixedVal) !== JSON.stringify(localValue.value)) {
          localValue.value = fixedVal
        }
      },
      { deep: true }
    )

    const emitChange = () => {
      emit('update', localValue.value)
    }

    // 文件选择
    const openFileDialog = () => {
      browserVisible.value = true
    }

    const onFileSelected = (relPath) => {
      localValue.value = relPath
      emitChange()
      browserVisible.value = false
    }

    // 截图
    const openScreenshot = () => {
      if (screenshotTool.value) {
        screenshotTool.value.open()
      }
    }

    const onScreenshotSaved = (templateName) => {
      if (templateName) {
        localValue.value = templateName
        emitChange()
      }
    }

    // list_dict 操作
    const addListItem = () => {
      const newItem = {}
      if (props.config.sub) {
        for (const [key, subConfig] of Object.entries(props.config.sub)) {
          newItem[key] = subConfig.default !== undefined ? subConfig.default : ''
        }
      }
      localValue.value.push(newItem)
      emitChange()
    }

    const removeListItem = (index) => {
      localValue.value.splice(index, 1)
      emitChange()
    }

    onBeforeUnmount(() => {
      unwatch()
    })

    return {
      localValue,
      screenshotTool,
      browserVisible,
      fileBrowserRef,
      resolvedOptions,
      openFileDialog,
      onFileSelected,
      openScreenshot,
      onScreenshotSaved,
      emitChange,
      addListItem,
      removeListItem
    }
  }
}
</script>

<style scoped>
.param-renderer {
  margin-bottom: 8px;
}
.param-label {
  font-size: 13px;
  color: #cfd3e6;
  font-weight: 500;
  margin-bottom: 4px;
}
.param-control {
  width: 100%;
}

.file-selector {
  display: flex;
  gap: 6px;
  align-items: center;
}
.file-selector .el-input {
  flex: 1;
}

.list-int2,
.list-int4 {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.coord-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.coord-label {
  font-size: 12px;
  color: #8a8fa8;
  font-weight: 500;
  min-width: 14px;
}
.coord-item .el-input-number {
  width: 70px;
}

.dict-container {
  padding-left: 12px;
  border-left: 2px solid #3d3d5a;
  margin-top: 4px;
}
</style>