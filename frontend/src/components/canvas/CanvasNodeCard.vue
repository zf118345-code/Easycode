<!-- frontend/src/components/canvas/CanvasNodeCard.vue -->
<!--
    Shared node card for WorkflowCanvas + TopologyCanvas（两模式同一套代码/组件）。
    视觉与结构完全一致；内容区由 config/nodeRegistry.js 的 content 规则驱动：
      无内容 → 高度 0（仅剩网格取整松弛区）；有内容 → 按类型渲染并参与高度估算。

    Port layout (grid-based):
      - entry   : LEFT  (target) — where an incoming edge lands
      - success : RIGHT (primary exit, green), 1 grid from top
      - failure : RIGHT (failure exit, red), 1 grid from bottom
      - branch_N / exit_N : stacked on the right, 2 grids apart
-->
<template>
    <div
        :class="['canvas-node-card', {
            'is-selected': selected,
            'is-active-debug': isActiveDebug
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
            <div class="node-header-left" :data-node-id="node.node_id">
                <component :is="nodeIcon" class="node-type-icon" />
                <span class="node-title" :data-node-id="node.node_id">{{ node.node_name }}</span>
            </div>
            <span v-if="isActiveDebug" class="node-debug-tag" title="当前执行命中此节点">
                <CirclePlay class="debug-pulse-icon" />
            </span>
            <!-- 断点槽：标题栏右侧（未设置=空心环，已设置=实心红点，命中=脉冲） -->
            <span
                class="node-breakpoint-gutter"
                :class="{ active: hasBreakpoint }"
                :title="hasBreakpoint ? '点击移除断点' : '点击设置断点'"
                @click.stop="$emit('toggle-breakpoint', node.node_id)">
                <span v-if="hasBreakpoint" class="bp-dot" />
            </span>
        </div>

        <!-- 2. Body — 注册表驱动的内容区（无内容时高度为 0） -->
        <div class="node-body" :data-node-id="node.node_id">
            <!-- 图像识别：模板缩略图（保持宽高比，最小高度 80px） -->
            <div v-if="contentKind === 'image'" class="node-image-embedded">
                <img
                    v-if="node.params?.image_source"
                    :src="imageThumbUrl"
                    :class="['embedded-template-img', { 'is-contain': isSpecialTallImage }]"
                    alt="模板"
                    @load="onImageLoaded"
                    @error="$event.target.style.display = 'none'" />
                <div v-else class="embedded-placeholder">
                    <ImageIcon class="embedded-icon" style="width: 18px; height: 18px;" />
                    <span>未选模板</span>
                </div>
            </div>

            <!-- OCR 识别：模板缩略图 + 识别配置行（最小高度 60px） -->
            <div v-else-if="contentKind === 'ocr'" class="ocr-preview-block">
                <img
                    v-if="node.params?.image_source"
                    :src="imageThumbUrl"
                    class="ocr-thumb"
                    alt="OCR 模板"
                    @error="$event.target.style.display = 'none'" />
                <div v-else class="ocr-thumb ocr-thumb-placeholder">
                    <ImageIcon style="width: 16px; height: 16px;" />
                </div>
                <div class="ocr-info-col">
                    <div class="node-info">
                        <span class="info-label">保存到</span>{{ node.params?.save_to_var || '未设置' }}
                    </div>
                    <div class="node-info">
                        <span class="info-label">区域</span>{{ regionText }}
                    </div>
                </div>
            </div>

            <!-- 分支：候选条件列表（每候选一行，动态计算高度） -->
            <div v-else-if="contentKind === 'branch-candidates'" class="branch-candidates-list">
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

            <!-- 页面状态：页面特征 / 出口预览（有才显示，数据内嵌 params） -->
            <div v-else-if="contentKind === 'page-info'" class="page-info-list">
                <div v-if="node.params?.page_id" class="node-info">
                    <span class="info-label">页面:</span>{{ node.params.page_id }}
                </div>
                <div v-if="node.params?.features && node.params.features.length" class="node-info">
                    <span class="info-label">特征:</span>{{ node.params.features.length }} 个 ({{ node.params.feature_mode || 'and' }})
                </div>
                <div v-if="node.params?.exits && node.params.exits.length" class="node-info">
                    <span class="info-label">出口:</span>{{ node.params.exits.length }} 个
                </div>
            </div>
        </div>

        <!-- 3. Footer bar（两模式一致） -->
        <div class="node-footer-bar" :data-node-id="node.node_id">
            <span class="footer-tag">延时: {{ node.delay_before ?? 200 }}ms</span>
            <span class="footer-tag">循环: {{ node.loop_count ?? 1 }}次</span>
        </div>

        <!-- 4. Ports / handles（网格布局：左缘入口、右缘成功/失败/动态出口，间距 2 格） -->
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
            :title="'成功出口 (success)'"
            @mousedown.stop="$emit('start-connection', $event, node.node_id, 'succ')" />

        <!-- Failure exit — right, 1 grid from bottom (conditional) -->
        <div
            v-if="node.ports?.failure?.visible"
            class="node-handle source-handle fail-handle"
            :class="{ 'is-unconnected': !node.ports?.failure?.connected }"
            :style="{ top: portTop('failure') }"
            :title="node.node_type === 'branch' ? 'Else 兜底出口' : '失败出口 (failure)'"
            @mousedown.stop="$emit('start-connection', $event, node.node_id, 'fail')" />

        <!-- Dynamic exits — right, 2 grids apart, 与节点高度联动 -->
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
    import { getNodeContentSpec } from '@/config/nodeRegistry'
    import { useMainStore } from '@/stores'

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

    const store = useMainStore()

    const headerStyle = computed(() => {
        const config = getNodeConfig(props.node.node_type, store.paramsDefinitions)
        return { '--node-accent': config.color }
    })

    const cardStyle = computed(() => ({
        left:   props.node.position.x + 'px',
        top:    props.node.position.y + 'px',
        width:  props.node.w + 'px',
        height: props.node.h + 'px'
    }))

    // 内容区展示规则（注册表驱动；null = 无内容，高度为 0）
    const contentSpec = computed(() => getNodeContentSpec(props.node.node_type))
    const contentKind = computed(() => contentSpec.value?.kind || null)

    // 端口距卡片顶部的像素偏移（网格坐标，与 getPortPosition 共用同一公式，随 node.h 联动）
    const portTop = (portType) => `${getNodePortTop(props.node, portType)}px`

    const _iconRegistry = {
        MousePointerClick, Timer, ScrollText, Image: ImageIcon, Type, GitBranch,
        Filter, Variable, Code, AppWindow, MapPin, Navigation, Square,
        Clock, SearchCheck, Binary, ListOrdered, FileCode, Target
    }

    const nodeIcon = computed(() => {
        const config = getNodeConfig(props.node.node_type, store.paramsDefinitions)
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

    const regionText = computed(() => {
        const region = props.node.params?.region_value
        if (!Array.isArray(region) || !region.length) return '未设置'
        return `[${region.join(', ')}]`
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
