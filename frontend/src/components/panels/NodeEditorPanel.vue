<template>
  <div class="node-editor-panel">
    <div v-if="store.selectedNode" class="editor-form">
      <div class="node-title">
        <span class="node-type-badge">{{ nodeTypeLabel }}</span>
        <span class="node-name">{{ store.selectedNode.node_name }}</span>
      </div>

      <el-divider content-position="left">参数配置</el-divider>
      <div class="params-container">
        <!-- 遍历所有参数 -->
        <template v-for="(config, paramName) in allParams" :key="paramName">
          <!-- 如果是 region_value，根据 region_type 决定是否显示 -->
          <div
            v-if="paramName === 'region_value'"
            v-show="shouldShowRegionValue"
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
import axios from 'axios'

// 定义需要展示跳转配置的节点类型
const JUDGMENT_NODE_TYPES = ['image_recognition', 'branch']

export default {
  name: 'NodeEditorPanel',
  components: { ParamRenderer },
  setup() {
    const store = useMainStore()

    // 当前节点的参数定义
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

    // 判断当前节点是否属于需要跳转配置的节点
    const isJudgmentNode = computed(() => {
      const node = store.selectedNode
      if (!node) return false
      return JUDGMENT_NODE_TYPES.includes(node.node_type)
    })

    // ===== 渲染上下文 =====
    const renderContext = computed(() => ({
      tasks: store.tasks || [],
      nodes: store.nodes || [],
      currentTaskId: store.currentTaskId,
      currentProject: store.currentProject
    }))

    // ===== allParams：所有参数（用于遍历） =====
    const allParams = computed(() => {
      return paramDefs.value
    })

    // ===== 是否显示 region_value =====
    const shouldShowRegionValue = computed(() => {
      const node = store.selectedNode
      if (!node) return false
      const regionType = node.params?.region_type
      return regionType && regionType !== 'fullwindow'
    })

    // ===== 跳转类型配置（固定） =====
    const jumpTypeConfig = {
      type: 'select',
      options: ['next', 'node', 'task', 'end'],
      default: 'next',
      label: '跳转类型'
    }

    // ===== 动态生成 target 配置 =====
    const getTargetConfig = (jumpKey) => ({
      type: 'select',
      options: (context, currentValue) => {
        const jumpType = store.selectedNode?.params?.[jumpKey]?.type || 'next'
        if (jumpType === 'task') {
          return (context.tasks || []).map(t => t.task_id)
        } else if (jumpType === 'node') {
          return (context.nodes || []).map(n => n.node_id)
        }
        return ['']
      },
      default: '',
      label: '目标'
    })

    // ===== 动态生成 target_node 配置 =====
    const getTargetNodeConfig = (jumpKey) => ({
      type: 'select',
      options: (context, currentValue) => {
        // 这里暂时返回空，因为需要根据 target 动态加载任务节点
        // 实际使用时，用户选择 target 后，target_node 会变为可选，但需要从后端获取
        return []
      },
      default: '',
      label: '目标节点'
    })

    // ===== 更新普通参数 =====
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

    // ===== 更新跳转参数 =====
    const updateJumpParam = (jumpKey, subKey, value) => {
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
      }
    }

    // ===== 保存节点 =====
    const saveNode = async () => {
      try {
        await store.saveCurrentTask(true)
        ElMessage.success('参数已保存')
      } catch (err) {
        console.error('保存失败', err)
        ElMessage.error('保存失败')
      }
    }

    // ===== 监听 region_type =====
    const unwatchRegionType = watch(
      () => store.selectedNode?.params?.region_type,
      async (newVal, oldVal) => {
        const node = store.selectedNode
        if (!node) return
        if (newVal === 'recorded' && newVal !== oldVal) {
          const templateName = node.params.image_source
          if (!templateName) {
            ElMessage.warning('请先选择模板图片')
            return
          }
          try {
            const res = await axios.get(`/api/projects/${store.currentProject}/regions`)
            const regions = res.data || {}
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
          }
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
      allParams,                   // ← 添加这个
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