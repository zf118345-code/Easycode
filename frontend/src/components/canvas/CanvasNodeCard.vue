<!-- frontend/src/components/canvas/CanvasNodeCard.vue -->
<template>
    <div
        :class="['canvas-node-card', { 'is-selected': selected, 'is-active-debug': isActiveDebug }]"
        :style="{ left: node.position.x + 'px', top: node.position.y + 'px', width: node.w + 'px', height: node.h + 'px' }"
        @mousedown.stop="$emit('node-mousedown', $event, node)"
        @mouseup="$emit('node-mouseup', $event, node)"
        @dblclick.stop="$emit('node-dblclick', $event, node)"
        @contextmenu.prevent.stop="$emit('node-contextmenu', $event, node)">

        <!-- 1. 卡片头部 -->
        <div class="node-header" :data-node-id="node.node_id">
            <span
                class="node-breakpoint-gutter"
                :class="{ active: hasBreakpoint }"
                title="点击切换断点"
                @click.stop="$emit('toggle-breakpoint', node.node_id)">
                <span v-if="hasBreakpoint" class="bp-dot" />
            </span>
            <div class="node-header-left" :data-node-id="node.node_id">
                <component :is="nodeIcon" class="node-type-icon" />
                <span class="node-title" :data-node-id="node.node_id">{{ node.node_name }}</span>
            </div>
            <span v-if="isActiveDebug" class="node-debug-tag" title="当前执行命中此节点">
                <CirclePlay class="debug-pulse-icon" />
            </span>
        </div>

        <!-- 2. 卡片中间主体区 -->
        <div class="node-body" :data-node-id="node.node_id">
            <!-- 图像识别节点预览 -->
            <div
                v-if="node.node_type === 'image_recognition'"
                class="node-image-embedded"
                :style="node.params?.image_source ? { '--bg-image-url': `url(${imageThumbUrl})` } : {}">
                <img
                    v-if="node.params?.image_source"
                    :src="imageThumbUrl"
                    :class="['embedded-template-img', { 'is-contain': isSpecialTallImage }]"
                    alt="模板"
                    @load="onImageLoaded"
                    @error="$event.target.style.display = 'none'" />
                <div v-else class="embedded-placeholder">
                    <Image style="width: 16px; height: 16px; opacity: 0.5; margin-bottom: 2px;" />
                    <span>未选模板</span>
                </div>
            </div>

            <!-- 分支选择 Branch 节点 -->
            <div v-else-if="node.node_type === 'branch'" class="branch-candidates-list">
                <div
                    v-for="(cand, cIdx) in (node.params?.candidates || [])"
                    :key="cIdx"
                    class="branch-candidate-item">
                    <span class="branch-cand-text" :title="formatCondDesc(cand.condition || cand)">
                        {{ formatCondDesc(cand.condition || cand) }}
                    </span>
                    <div
                        class="node-handle source-handle branch-handle"
                        :title="`分支 ${cIdx + 1} 成立时流向出口`"
                        @mousedown.stop="$emit('start-connection', $event, node.node_id, `branch_${cIdx}`)" />
                </div>
                <div v-if="!node.params?.candidates?.length" class="empty-cand-placeholder">
                    <span>未配置分流条件</span>
                </div>
            </div>
        </div>

        <!-- 3. 卡片底部固定边栏 -->
        <div class="node-footer-bar" :data-node-id="node.node_id">
            <span class="footer-tag">延时: {{ node.delay_before ?? 200 }}ms</span>
            <span class="footer-tag">循环: {{ node.loop_count ?? 1 }}次</span>
        </div>

        <!-- 通用入口与失败/兜底锚点 -->
        <div class="node-handle target-handle top-handle" title="入口位置" />
        <div v-if="node.node_type !== 'branch'" class="node-handle source-handle succ-handle" title="成功流向出口" @mousedown.stop="$emit('start-connection', $event, node.node_id, 'succ')" />
        <div v-if="node.showFailPort" class="node-handle source-handle fail-handle" :title="node.node_type === 'branch' ? 'Else 兜底分支出口' : '失败分支出口'" @mousedown.stop="$emit('start-connection', $event, node.node_id, 'fail')" />
    </div>
</template>

<script setup>
    import { computed, reactive } from 'vue'
    import { CirclePlay, Image as ImageIcon } from 'lucide-vue-next'
    import { NODE_TYPE_CONFIG } from '@/utils/canvasShared'

    const props = defineProps({
        node: { type: Object, required: true },
        selected: { type: Boolean, default: false },
        isActiveDebug: { type: Boolean, default: false },
        hasBreakpoint: { type: Boolean, default: false },
        currentProjectPath: { type: String, default: '' },
        blueprintVersion: { type: [Number, String], default: 0 }
    })

    const emit = defineEmits([
        'node-mousedown',
        'node-mouseup',
        'node-dblclick',
        'node-contextmenu',
        'toggle-breakpoint',
        'start-connection',
        'image-loaded'
    ])

    // 图标组件缓存
    const _iconCache = { CirclePlay, Image: ImageIcon }
    const _iconComponentMap = {
        click: 'MousePointerClick',
        wait: 'Clock',
        set_window: 'Target',
        image_recognition: 'Image',
        ocr_recognition: 'FileSearch',
        branch: 'GitBranch',
        logic_check: 'SearchCheck',
        variable_op: 'Binary',
        log: 'ListOrdered',
        script_call: 'FileCode',
        smart_jump: 'Compass'
    }

    const nodeIcon = computed(() => {
        const config = NODE_TYPE_CONFIG[props.node.node_type]
        const iconName = config?.icon || _iconComponentMap[props.node.node_type]
        return _iconCache[iconName] || ImageIcon
    })

    // 图像高度追踪
    const tallImageFlags = reactive({})

    const isSpecialTallImage = computed(() => !!tallImageFlags[props.node.node_id])

    const imageThumbUrl = computed(() => {
        const imageSource = props.node.params?.image_source
        if (!imageSource) return ''
        let cleanName = imageSource.replace(/\\/g, '/')
        if (!/\.(png|jpg|jpeg)$/i.test(cleanName)) cleanName += '.png'
        return `/api/image/thumb?project_path=${encodeURIComponent(props.currentProjectPath || '')}&name=${encodeURIComponent(cleanName)}&v=${props.blueprintVersion}`
    })

    const onImageLoaded = (e) => {
        const img = e.target
        const naturalW = img.naturalWidth || 100
        const naturalH = img.naturalHeight || 100
        const cardInnerWidth = props.node.w - 24
        const ratio = naturalH / naturalW
        if (ratio > 1) {
            tallImageFlags[props.node.node_id] = true
        }
        emit('image-loaded', { nodeId: props.node.node_id, width: naturalW, height: naturalH, cardInnerWidth })
    }

    // 格式化条件描述
    const formatCondDesc = (item) => {
        if (!item) return '未配置条件'
        const condType = item.condition_type || item.type || 'variable_check'
        const params = item.params || item

        if (condType === 'image_exists') {
            const opText = params.exist_mode === 'not_exists' ? '不存在' : '存在'
            return `${opText}: ${params.image_source || '未选图片'}`
        }
        if (condType === 'text_contains') {
            return `文本: ${params.target_text || '未设文本'}`
        }
        if (condType === 'variable_check') {
            return `变量: ${params.variable_name || params.var_name || '未选'} (${params.operator || 'eq'}) ${params.compare_value ?? params.target_value ?? ''}`
        }
        if (condType === 'window_state') {
            return `窗口: ${params.window_title || '默认'} (${params.state_check || '存在'})`
        }
        if (condType === 'file_exists') {
            return `文件: ${params.file_path || '未设路径'}`
        }
        return `判定: ${condType}`
    }
</script>
