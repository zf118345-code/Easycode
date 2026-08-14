<!-- frontend/src/components/inspector/panels/BatchInspectorPanel.vue -->
<template>
    <div class="panel-layout-root">
        <!-- 1. 顶部 Files 图标 + 100% 还原单选视觉样式的标题 Input -->
        <div class="inspector-fixed-header">
            <div class="node-title-box">
                <div class="node-type-icon-badge" title="批量编辑">
                    <Files class="inspector-type-svg" />
                </div>
                <el-input
:model-value="`批量编辑已选中的 ${nodes.length} 个节点`"
                          readonly
                          size="default"
                          class="node-name-input batch-title-input" />
            </div>
        </div>

        <!-- 2. 中间共有属性渲染区 -->
        <div class="inspector-scrollable-body">
            <div class="params-container">
                <template v-for="(config, paramName) in commonParams" :key="paramName">
                    <div v-if="!['region_value', 'gray_threshold', 'on_success', 'on_failure', 'candidates'].includes(paramName)" class="param-item">
                        <ParamRenderer
:config="config"
                                       :value="getCommonParamValue(paramName)"
                                       :label="config.label || paramName"
                                       :context="{}"
                                       @update="val => handleBatchParamUpdate(paramName, val)"
                                       @auto-change-type="inferredType => handleBatchParamUpdate('var_type', inferredType)" />
                    </div>
                </template>

                <div v-if="Object.keys(commonParams).length === 0" class="inspector-empty-tip">
                    <span>所选节点无公共可配置属性</span>
                </div>
            </div>
        </div>

        <!-- 3. 底部批量延迟/循环次数 -->
        <div class="inspector-fixed-footer">
            <div class="footer-inline-container">
                <div class="footer-setting-group">
                    <span class="footer-label">延迟</span>
                    <el-input v-model.number="batchDelay" size="small" class="pure-compact-input" />
                    <span class="footer-unit">ms</span>
                </div>
                <div class="footer-setting-group">
                    <span class="footer-label">循环</span>
                    <el-input v-model.number="batchLoop" size="small" class="pure-compact-input" />
                    <span class="footer-unit">次</span>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
    import { computed } from 'vue'
    import { useMainStore } from '@/stores'
    import ParamRenderer from '@/components/ParamRenderer.vue'
    import { Files } from 'lucide-vue-next'

    const props = defineProps({
        nodes: { type: Array, default: () => [] }
    })
    const emit = defineEmits(['save'])
    const store = useMainStore()

    const commonParams = computed(() => {
        if (!props.nodes || props.nodes.length === 0) return {}
        const paramDefsList = props.nodes.map(n => store.paramsDefinitions[n.node_type]?.params || {})
        if (paramDefsList.length === 0) return {}

        const firstDefs = paramDefsList[0]
        const common = {}
        for (const [key, config] of Object.entries(firstDefs)) {
            const isCommon = paramDefsList.every(defs => Object.prototype.hasOwnProperty.call(defs, key))
            if (isCommon) common[key] = config
        }
        return common
    })

    const getCommonParamValue = (paramName) => {
        if (!props.nodes || props.nodes.length === 0) return ''
        const firstVal = props.nodes[0].params?.[paramName]
        const allSame = props.nodes.every(n => JSON.stringify(n.params?.[paramName]) === JSON.stringify(firstVal))
        return allSame ? firstVal : ''
    }

    const handleBatchParamUpdate = (paramName, value) => {
        const ids = props.nodes.map(n => n.node_id)
        store.blueprint?.tasks?.forEach(t => {
            (t.nodes || []).forEach(n => {
                if (ids.includes(n.node_id)) {
                    if (!n.params) n.params = {}
                    n.params[paramName] = value
                }
            })
        })
        emit('save')
    }

    const batchDelay = computed({
        get: () => {
            if (!props.nodes || props.nodes.length === 0) return 200
            const firstVal = props.nodes[0].delay_before ?? 200
            const allSame = props.nodes.every(n => (n.delay_before ?? 200) === firstVal)
            return allSame ? firstVal : ''
        },
        set: (val) => {
            const num = Number(val) || 0
            const ids = props.nodes.map(n => n.node_id)
            store.blueprint?.tasks?.forEach(t => {
                (t.nodes || []).forEach(n => {
                    if (ids.includes(n.node_id)) n.delay_before = num
                })
            })
            emit('save')
        }
    })

    const batchLoop = computed({
        get: () => {
            if (!props.nodes || props.nodes.length === 0) return 1
            const firstVal = props.nodes[0].loop_count ?? 1
            const allSame = props.nodes.every(n => (n.loop_count ?? 1) === firstVal)
            return allSame ? firstVal : ''
        },
        set: (val) => {
            const num = Number(val) || 1
            const ids = props.nodes.map(n => n.node_id)
            store.blueprint?.tasks?.forEach(t => {
                (t.nodes || []).forEach(n => {
                    if (ids.includes(n.node_id)) n.loop_count = num
                })
            })
            emit('save')
        }
    })
</script>

<style scoped>
    .panel-layout-root {
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
    }

    .inspector-fixed-header {
        padding: 12px 14px;
        background: rgba(25, 26, 38, 0.95);
        border-bottom: 1px solid var(--el-border-color-light);
        flex-shrink: 0;
    }

    .node-title-box {
        display: flex;
        align-items: center;
        gap: 10px;
    }

    .node-type-icon-badge {
        width: 32px;
        height: 32px;
        background: rgba(78, 209, 156, 0.1);
        border: 1px solid rgba(78, 209, 156, 0.3);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }

    .inspector-type-svg {
        width: 18px;
        height: 18px;
        color: var(--el-color-primary);
    }

    .batch-title-input {
        flex: 1;
    }

        .batch-title-input :deep(.el-input__wrapper) {
            cursor: default !important;
            background-color: transparent !important;
            box-shadow: none !important;
            border: none !important;
            padding-left: 0 !important;
        }

        .batch-title-input :deep(.el-input__inner) {
            cursor: default !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            color: var(--el-text-color-primary) !important;
        }

    .inspector-scrollable-body {
        flex: 1;
        padding: 12px 14px;
        overflow-y: auto;
        overscroll-behavior: contain;
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

    .inspector-empty-tip {
        padding: 30px 0;
        text-align: center;
        font-size: 12px;
        color: var(--el-text-color-placeholder);
    }

    .inspector-fixed-footer {
        padding: 10px 14px;
        background: rgba(25, 26, 38, 0.95);
        border-top: 1px solid var(--el-border-color-light);
        flex-shrink: 0;
    }

    .footer-inline-container {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .footer-setting-group {
        display: flex;
        align-items: center;
        gap: 6px;
        font-size: 12px;
        color: var(--el-text-color-regular);
    }

    .footer-label {
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .footer-unit {
        font-size: 11px;
        color: var(--el-text-color-secondary);
    }

    .pure-compact-input {
        width: 60px !important;
    }

        .pure-compact-input :deep(.el-input__wrapper) {
            padding-left: 4px !important;
            padding-right: 4px !important;
            background-color: var(--el-fill-color-blank) !important;
        }
</style>