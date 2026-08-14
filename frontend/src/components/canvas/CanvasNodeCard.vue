<!-- frontend/src/components/canvas/CanvasNodeCard.vue -->
<!--
    Shared node card for WorkflowCanvas + TopologyCanvas.
    The visual appearance is identical between the two modes.
    Only the body content and port visibility differ (driven by the `mode` prop).

    Port layout (industry standard):
      - entry   : LEFT  (target) — where an incoming edge lands
      - success : BOTTOM (primary exit, green)
      - failure : RIGHT  (failure exit, red)
      - branch_N / exit_N : stacked on the right side
-->
<template>
    <div
        :class="['canvas-node-card', {
            'is-selected': selected,
            'is-active-debug': isActiveDebug,
            'is-topology': mode === 'topology'
        }]"
        :style="cardStyle"
        :data-node-id="node.node_id"
        @mousedown.stop="$emit('node-mousedown', $event, node)"
        @mouseup="$emit('node-mouseup', $event, node)"
        @dblclick.stop="$emit('node-dblclick', $event, node)"
        @contextmenu.prevent.stop="$emit('node-contextmenu', $event, node)">
<!-- 1. Header with accent color (per-type) -->
        <div
            class="node-header"
            :style="headerStyle"
            :data-node-id="node.node_id">
            <span
                class="node-breakpoint-gutter"
                :class="{ active: hasBreakpoint && mode !== 'topology', 'is-placeholder': mode === 'topology' }"
                :title="mode !== 'topology' ? '点击切换断点' : ''"
                @click.stop="mode !== 'topology' && $emit('toggle-breakpoint', node.node_id)">
                <span v-if="hasBreakpoint && mode !== 'topology'" class="bp-dot" />
            </span>
            <div class="node-header-left" :data-node-id="node.node_id">
                <component :is="nodeIcon" class="node-type-icon" />
                <span class="node-title" :data-node-id="node.node_id">{{ node.node_name }}</span>
            </div>
            <span v-if="isActiveDebug" class="node-debug-tag" title="当前执行命中此节点">
                <CirclePlay class="debug-pulse-icon" />
            </span>
        </div>

        <!-- 2. Body — mode-specific content -->
        <div
            class="node-body"
            :class="{ 'is-scrollable': (node.ports?.dynamic?.length || 0) > 10 }"
            :data-node-id="node.node_id">
            <!-- Topology mode body -->
            <template v-if="mode === 'topology'">
                <div v-if="node.node_type === 'page_state' && node.page_id" class="node-info">
                    <span class="info-label">页面:</span> {{ node.page_id }}
                </div>
                <div v-if="node.features && node.features.length" class="node-info">
                    <span class="info-label">特征:</span> {{ node.features.length }} 个 ({{ node.feature_mode || 'and' }})
                </div>
                <div v-if="node.exits && node.exits.length" class="node-info">
                    <span class="info-label">出口:</span> {{ node.exits.length }} 个
                </div>
                <div v-if="node.node_type === 'smart_jump' && node.target_page" class="node-info">
                    <span class="info-label">跳转至:</span> {{ node.target_page }}
                </div>
            </template>

            <!-- Workflow mode: image recognition preview -->
            <div
                v-else-if="node.node_type === 'image_recognition'"
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
                    <Image class="embedded-icon" style="width: 18px; height: 18px; opacity: 0.5;" />
                    <span>未选模板</span>
                </div>
            </div>

            <!-- Workflow mode: branch candidates -->
            <div v-else-if="node.node_type === 'branch'" class="branch-candidates-list">
                <div
                    v-for="(cand, cIdx) in (node.params?.candidates || [])"
                    :key="cIdx"
                    class="branch-candidate-item">
                    <span class="branch-cand-text" :title="formatCondDesc(cand.condition || cand)">
                        {{ formatCondDesc(cand.condition || cand) }}
                    </span>
                </div>
                <div v-if="!node.params?.candidates?.length" class="empty-cand-placeholder">
                    未配置分流条件
                </div>
            </div>

            <!-- Workflow mode: generic info display -->
            <template v-else-if="mode !== 'topology'">
                <div v-if="node.node_type === 'log' && node.params?.message" class="node-info">
                    <span class="info-label">日志:</span> {{ truncateText(node.params.message, 28) }}
                </div>
                <div v-if="node.node_type === 'logic_check' && node.params?.condition_type" class="node-info">
                    <span class="info-label">条件:</span> {{ node.params.condition_type }}
                </div>
                <div v-if="node.node_type === 'variable_op' && node.params?.variable_name" class="node-info">
                    <span class="info-label">变量:</span> {{ node.params.variable_name }}
                </div>
                <div v-if="node.node_type === 'script_call' && node.params?.script_name" class="node-info">
                    <span class="info-label">脚本:</span> {{ node.params.script_name }}
                </div>
                <div v-if="node.node_type === 'click' && node.params?.selector" class="node-info">
                    <span class="info-label">选择器:</span> {{ truncateText(node.params.selector, 24) }}
                </div>
            </template>
        </div>

        <!-- 3. Footer bar (workflow mode only) -->
        <div v-if="mode !== 'topology'" class="node-footer-bar" :data-node-id="node.node_id">
            <span class="footer-tag">延时: {{ node.delay_before ?? 200 }}ms</span>
            <span class="footer-tag">循环: {{ node.loop_count ?? 1 }}次</span>
        </div>

        <!-- 4. Ports / handles（网格布局：左缘入口、右缘成功/失败/动态出口） -->
        <!-- Entry target on the left, 1 grid from top (always visible) -->
        <div
            class="node-handle entry-handle"
            :style="{ top: portTop('entry') }"
            title="入口 (entry)" />

        <!-- Success exit — right, 1 grid from top -->
        <div
            v-if="node.ports?.success?.visible !== false"
            class="node-handle source-handle succ-handle"
            :class="{ 'is-unconnected': !node.ports?.success?.connected }"
            :style="{ top: portTop('success') }"
            :title="mode === 'topology' ? '主出口 (success)' : '成功出口 (success)'"
            @mousedown.stop="$emit('start-connection', $event, node.node_id, 'succ')" />

        <!-- Failure exit — right, 1 grid from bottom (conditional) -->
        <div
            v-if="node.ports?.failure?.visible"
            class="node-handle source-handle fail-handle"
            :class="{ 'is-unconnected': !node.ports?.failure?.connected }"
            :style="{ top: portTop('failure') }"
            :title="node.node_type === 'branch' ? 'Else 兜底出口' : '失败出口 (failure)'"
            @mousedown.stop="$emit('start-connection', $event, node.node_id, 'fail')" />

        <!-- Dynamic exits — right, 1 grid step between success and failure -->
        <div
            v-for="port in (node.ports?.dynamic || [])"
            :key="port.name"
            class="node-handle source-handle dyn-handle"
            :class="{ 'is-unconnected': !port.connected }"
            :style="{ top: portTop(port.name) }"
            :title="port.label"
            @mousedown.stop="$emit('start-connection', $event, node.node_id, port.name)" />
    </div>
</template>

<script setup>
    import { computed, reactive } from 'vue'
    import {
        CirclePlay,
        Image as ImageIcon,
        MousePointerClick,
        Timer,
        ScrollText,
        Type,
        GitBranch,
        Filter,
        Variable,
        Code,
        AppWindow,
        MapPin,
        Navigation,
        Square,
        SearchCheck,
        Binary,
        ListOrdered,
        FileCode,
        Target,
        Clock
    } from 'lucide-vue-next'
    import { getNodeConfig, getNodePortTop } from '@/utils/canvasShared'

    const props = defineProps({
        node:              { type: Object,  required: true },
        selected:          { type: Boolean, default: false },
        isActiveDebug:     { type: Boolean, default: false },
        hasBreakpoint:     { type: Boolean, default: false },
        currentProjectPath:{ type: String,  default: '' },
        blueprintVersion:  { type: [Number, String], default: 0 },
        mode:              { type: String,  default: 'workflow' }
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

    const headerStyle = computed(() => {
        const config = getNodeConfig(props.node.node_type)
        return { '--node-accent': config.color }
    })

    const cardStyle = computed(() => ({
        left:   props.node.position.x + 'px',
        top:    props.node.position.y + 'px',
        width:  props.node.w + 'px',
        height: props.node.h + 'px'
    }))

    // 端口距卡片顶部的像素偏移（网格坐标，与 getPortPosition 共用同一公式）
    const portTop = (portType) => `${getNodePortTop(props.node, portType)}px`

    const _iconRegistry = {
        MousePointerClick, Timer, ScrollText, Image: ImageIcon, Type, GitBranch,
        Filter, Variable, Code, AppWindow, MapPin, Navigation, Square,
        Clock, SearchCheck, Binary, ListOrdered, FileCode, Target
    }

    const nodeIcon = computed(() => {
        const config = getNodeConfig(props.node.node_type)
        const iconName = config?.icon || 'Square'
        return _iconRegistry[iconName] || Square
    })

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
        if (ratio > 1) tallImageFlags[props.node.node_id] = true
        emit('image-loaded', { nodeId: props.node.node_id, width: naturalW, height: naturalH, cardInnerWidth })
    }

    const truncateText = (text, maxLen) => {
        if (!text) return ''
        return text.length > maxLen ? text.slice(0, maxLen) + '...' : text
    }

    const formatCondDesc = (item) => {
        if (!item) return '未配置条件'
        const condType = item.condition_type || item.type || 'variable_check'
        const params = item.params || item
        if (condType === 'image_exists') {
            const opText = params.exist_mode === 'not_exists' ? '不存在' : '存在'
            return `${opText}: ${params.image_source || '未选图片'}`
        }
        if (condType === 'text_contains') return `文本: ${params.target_text || '未设文本'}`
        if (condType === 'variable_check') {
            return `变量: ${params.variable_name || params.var_name || '未选'} (${params.operator || 'eq'}) ${params.compare_value ?? params.target_value ?? ''}`
        }
        if (condType === 'window_state') return `窗口: ${params.window_title || '默认'} (${params.state_check || '存在'})`
        if (condType === 'file_exists') return `文件: ${params.file_path || '未设路径'}`
        return `判定: ${condType}`
    }
</script>

<style scoped>
    .embedded-icon {
        margin-bottom: 4px;
        opacity: 0.6;
    }
</style>
