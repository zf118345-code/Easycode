<template>
  <div class="node-editor-panel">
    <div v-if="store.selectedNode" class="editor-form">
      <div class="node-title">
        <span class="node-type-badge">{{ nodeTypeLabel }}</span>
        <span class="node-name">{{ store.selectedNode.node_name }}</span>
      </div>

      <el-divider content-position="left">参数配置</el-divider>
      <div class="params-container">
        <!-- 遍历所有参数，并控制 region_value 的显示 -->
        <template v-for="(config, paramName) in allParams" :key="paramName">
          <!-- 如果是 region_value，根据 region_type 决定是否显示 -->
          <div
            v-if="paramName === 'region_value'"
            v-show="store.selectedNode.params.region_type !== 'fullwindow'"
            class="param-item"
          >
            <ParamRenderer
              :config="config"
              :value="store.selectedNode.params.region_value"
              :label="config.label || paramName"
              :context="renderContext"
              @update="(val) => updateParam(paramName, val)"
            />
          </div>
          <!-- 其他参数正常渲染（但排除 on_success 和 on_failure，由跳转区域单独处理） -->
          <div
            v-else-if="paramName !== 'on_success' && paramName !== 'on_failure'"
            class="param-item"
          >
            <ParamRenderer
              :config="config"
              :value="store.selectedNode.params[paramName]"
              :label="config.label || paramName"
              :context="renderContext"
              @update="(val) => updateParam(paramName, val)"
            />
          </div>
        </template>

        <!-- 跳转配置（仅判断节点） -->
        <template v-if="isJudgmentNode">
          <div v-for="jumpKey in ['on_success', 'on_failure']" :key="jumpKey" class="jump-section">
            <el-divider content-position="left">
              {{ jumpKey === 'on_success' ? '成功跳转' : '失败跳转' }}
            </el-divider>
            <div class="jump-config">
              <div class="param-item">
                <ParamRenderer
                  :config="jumpTypeConfig"
                  :value="store.selectedNode.params[jumpKey]?.type || 'next'"
                  label="跳转类型"
                  :context="renderContext"
                  @update="(val) => updateJumpParam(jumpKey, 'type', val)"
                />
              </div>
              <div v-if="['node', 'task'].includes(store.selectedNode.params[jumpKey]?.type || 'next')" class="param-item">
                <ParamRenderer
                  :config="getTargetConfig(jumpKey)"
                  :value="store.selectedNode.params[jumpKey]?.target || ''"
                  :label="store.selectedNode.params[jumpKey]?.type === 'task' ? '目标任务' : '目标节点'"
                  :context="renderContext"
                  @update="(val) => updateJumpParam(jumpKey, 'target', val)"
                />
              </div>
              <div v-if="store.selectedNode.params[jumpKey]?.type === 'task' && store.selectedNode.params[jumpKey]?.target" class="param-item">
                <ParamRenderer
                  :config="getTargetNodeConfig(jumpKey)"
                  :value="store.selectedNode.params[jumpKey]?.target_node || ''"
                  label="目标节点"
                  :context="renderContext"
                  @update="(val) => updateJumpParam(jumpKey, 'target_node', val)"
                />
              </div>
            </div>
          </div>
        </template>
      </div>

      <div class="save-actions">
        <el-button type="primary" size="small" @click="saveNode">保存参数</el-button>
      </div>
    </div>
    <div v-else class="empty">请从节点列表中选择一个节点</div>
  </div>
</template>

<script>
import { useMainStore } from '@/stores'
import { computed, watch, onBeforeUnmount } from 'vue'
import ParamRenderer from '@/components/ParamRenderer.vue'
import { ElMessage } from 'element-plus'

const JUDGMENT_NODE_TYPES = ['image_recognition', 'branch']

export default {
  name: 'NodeEditorPanel',
  components: { ParamRenderer },
  setup() {
    const store = useMainStore()

    const paramDefs = computed(() => {
      const node = store.selectedNode
      if (!node) return {}
      return store.params[node.node_type]?.params || {}
    })

    const nodeTypeLabel = computed(() => {
      const node = store.selectedNode
      if (!node) return ''
      return store.params[node.node_type]?.label || node.node_type
    })

    const isJudgmentNode = computed(() => {
      const node = store.selectedNode
      if (!node) return false
      return JUDGMENT_NODE_TYPES.includes(node.node_type)
    })

    const renderContext = computed(() => ({
      tasks: store.tasks || [],
      nodes: store.nodes || [],
      currentTaskId: store.currentTaskId,
      currentProject: store.currentProjectPath,   // 改为 project_path
      taskNodesCache: store.taskNodesCache || {}
    }))

    const allParams = computed(() => paramDefs.value)

    const shouldShowRegionValue = computed(() => {
      const node = store.selectedNode
      if (!node) return false
      const regionType = node.params?.region_type
      return regionType && regionType !== 'fullwindow'
    })

    const jumpTypeConfig = {
      type: 'select',
      options: ['next', 'node', 'task', 'end'],
      default: 'next',
      label: '跳转类型'
    }

    const getTargetConfig = (jumpKey) => ({
      type: 'select',
      options: (context, currentValue) => {
        const jumpType = context?.currentJumpType || store.selectedNode?.params?.[jumpKey]?.type || 'next'
        if (jumpType === 'task') {
          return (context?.tasks || store.tasks || []).map(t => t.task_id)
        } else if (jumpType === 'node') {
          return (context?.nodes || store.nodes || []).map(n => n.node_id)
        }
        return ['']
      },
      default: '',
      label: '目标'
    })

    const getTargetNodeConfig = (jumpKey) => ({
      type: 'select',
      options: async (context, currentValue) => {
        const jumpData = store.selectedNode?.params?.[jumpKey]
        if (!jumpData) return ['']
        const taskId = jumpData.target
        if (!taskId) return ['']
        const cached = store.taskNodesCache?.[taskId]
        if (cached) return cached.map(n => n.node_id)
        try {
          const nodes = await store.loadTaskNodes(taskId)
          return nodes.map(n => n.node_id)
        } catch (err) {
          console.error('加载任务节点失败', err)
          return ['']
        }
      },
      default: '',
      label: '目标节点'
    })

    const updateParam = (paramName, value) => {
      const node = store.selectedNode
      if (!node) return
      node.params[paramName] = value
      if (paramName === 'region_value' && node.params.region_type === 'recorded') {
        const originalValue = node._originalRegionValue
        if (originalValue && JSON.stringify(value) !== JSON.stringify(originalValue)) {
          node.params.region_type = 'custom'
          ElMessage.info('已切换到自定义模式')
        }
      }
    }

    const updateJumpParam = async (jumpKey, subKey, value) => {
      const node = store.selectedNode
      if (!node) return
      if (!node.params[jumpKey]) {
        node.params[jumpKey] = { type: 'next', target: '', target_node: '' }
      }
      node.params[jumpKey][subKey] = value
      if (subKey === 'type') {
        if (value === 'next' || value === 'end') {
          node.params[jumpKey].target = ''
          node.params[jumpKey].target_node = ''
        }
        if (value === 'node') {
          node.params[jumpKey].target_node = ''
        }
        if (value === 'task') {
          const tasks = store.tasks || []
          if (tasks.length && !node.params[jumpKey].target) {
            node.params[jumpKey].target = tasks[0].task_id
          }
        }
      }
      if (subKey === 'target' && node.params[jumpKey].type === 'task') {
        node.params[jumpKey].target_node = ''
        if (value) {
          await store.loadTaskNodes(value)
        }
      }
    }

    const saveNode = async () => {
      try {
        await store.saveCurrentTask(true)
        ElMessage.success('参数已保存')
      } catch (err) {
        console.error('保存失败', err)
        ElMessage.error('保存失败')
      }
    }

    // ====== 修复：加载 regions 使用 store.getRegions ======
    const loadRegionFromStorage = async (node) => {
      if (!store.currentProjectPath) {
        ElMessage.warning('请先打开项目')
        return
      }
      const templateName = node.params.image_source
      if (!templateName) {
        ElMessage.warning('请先选择模板图片')
        return
      }
      try {
        const regions = await store.getRegions()
        if (regions[templateName]) {
          node.params.region_value = regions[templateName]
          node._originalRegionValue = [...regions[templateName]]
        } else {
          node.params.region_value = [0, 0, 0, 0]
          node._originalRegionValue = [0, 0, 0, 0]
          ElMessage.warning('未找到该图片的区域配置，将使用全屏匹配')
        }
      } catch (err) {
        console.error('加载区域配置失败', err)
        ElMessage.error('加载区域配置失败')
      }
    }

    // 监听 region_type 变化
    const unwatchRegionType = watch(
      () => store.selectedNode?.params?.region_type,
      async (newVal, oldVal) => {
        const node = store.selectedNode
        if (!node) return
        if (newVal === 'recorded' && newVal !== oldVal) {
          await loadRegionFromStorage(node)
        }
      }
    )

    const unwatchImageSource = watch(
      () => store.selectedNode?.params?.image_source,
      (newVal, oldVal) => {
        if (newVal && newVal !== oldVal) {
          const node = store.selectedNode
          if (node?.params?.region_type === 'recorded') {
            const currentType = node.params.region_type
            node.params.region_type = 'fullwindow'
            setTimeout(() => {
              node.params.region_type = currentType
            }, 50)
          }
        }
      }
    )

    onBeforeUnmount(() => {
      unwatchRegionType()
      unwatchImageSource()
    })

    return {
      store,
      allParams,
      shouldShowRegionValue,
      isJudgmentNode,
      jumpTypeConfig,
      getTargetConfig,
      getTargetNodeConfig,
      nodeTypeLabel,
      renderContext,
      updateParam,
      updateJumpParam,
      saveNode
    }
  }
}
</script>

<style scoped>
.node-editor-panel {
  height: 100%;
  padding: 16px;
  overflow-y: auto;
}
.node-title {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}
.node-type-badge {
  background: #409EFF;
  color: white;
  padding: 2px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}
.node-name {
  color: #cfd3e6;
  font-size: 18px;
  font-weight: 600;
}
.params-container {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.param-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.jump-section {
  border-top: 1px solid #3d3d5a;
  padding-top: 12px;
  margin-top: 8px;
}
.jump-config {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-left: 12px;
}
.save-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #8a8fa8;
}
</style>