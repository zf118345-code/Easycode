<!-- frontend/src/components/TaskGroupNode.vue -->
<template>
    <div class="task-group-card app-card-dark"
         :class="{ 'is-current': isCurrentTask }"
         :style="{ transform: `translate(${position.x}px, ${position.y}px)` }"
         @mousedown="onCardMouseDown"
         @contextmenu.prevent.stop="onCardContextMenu">
        <!-- 卡片头部标题 -->
        <div class="task-card-header">
            <div class="task-title-area">
                <span class="task-badge">Group</span>
                <span class="task-name">{{ task.task_name || task.task_id }}</span>
            </div>
            <div class="task-header-btns">
                <el-button link size="small" type="primary" title="添加节点" @click.stop="$emit('addNode', task.task_id)">
                    ➕
                </el-button>
                <el-button link size="small" type="danger" title="删除任务组" @click.stop="$emit('deleteTask', task.task_id)">
                    🗑️
                </el-button>
            </div>
        </div>

        <!-- 节点列表区 -->
        <div class="node-list">
            <div v-for="(node, index) in (task.nodes || [])"
                 :key="node.node_id"
                 :id="`node-${node.node_id}`"
                 class="node-card-item"
                 :class="{
          'is-selected': selectedNodeId === node.node_id,
          'is-disabled': !node.enabled
        }"
                 @click.stop="$emit('selectNode', node.node_id)"
                 @contextmenu.prevent.stop="$emit('nodeContextMenu', { event: $event, task, node })">
                <!-- 1. 节点 Card Header -->
                <div class="node-item-header">
                    <div class="node-header-left">
                        <component :is="getNodeIcon(node.node_type)" class="node-type-icon" />
                        <span class="node-title">{{ node.node_name || node.node_id }}</span>
                    </div>
                    <span class="node-index-badge">#{{ index + 1 }}</span>
                </div>

                <!-- 2. 中间缩略图预览（适用于 image_recognition 节点） -->
                <div v-if="node.node_type === 'image_recognition'" class="node-body-image">
                    <div v-if="node.params?.image_source"
                         class="image-thumb-box"
                         :style="{ '--bg-url': `url(${getImageUrl(node.params.image_source)})` }">
                        <img :src="getImageUrl(node.params.image_source)"
                             class="thumb-img"
                             alt="模板缩略图"
                             @error="e => { e.target.style.display = 'none' }" />
                    </div>
                    <div v-else class="empty-thumb-box">
                        <span>未选模板图片</span>
                    </div>
                </div>

                <!-- 3. 卡片底部 Tag 区域 -->
                <div class="node-item-footer">
                    <span class="footer-tag">延时: {{ node.delay_before ?? 0 }}ms</span>
                    <span class="footer-tag">循环: {{ node.loop_count ?? 1 }}次</span>
                </div>

                <!-- 4. 连线锚点 -->
                <div class="anchor anchor-in" :data-node-id="node.node_id" data-anchor-type="in" />
                <div class="anchor anchor-out" :data-node-id="node.node_id" data-anchor-type="out" />
            </div>

            <div v-if="!task.nodes || !task.nodes.length" class="empty-node-tip">
                点击右上角 ➕ 添加节点
            </div>
        </div>
    </div>
</template>

<script setup>
    import { computed } from 'vue'
    import { useMainStore } from '@/stores'
    import {
        MousePointerClick, Clock, Target, FileSearch, GitBranch,
        SearchCheck, Binary, FileCode, Image
    } from 'lucide-vue-next'

    const props = defineProps({
        task: { type: Object, required: true },
        currentTaskId: { type: String, default: null },
        selectedNodeId: { type: String, default: null },
        position: { type: Object, default: () => ({ x: 100, y: 100 }) }
    })

    const emit = defineEmits([
        'selectNode',
        'addNode',
        'deleteTask',
        'cardMouseDown',
        'cardContextMenu',
        'nodeContextMenu'
    ])

    const store = useMainStore()

    const isCurrentTask = computed(() => props.currentTaskId === props.task.task_id)

    const getNodeIcon = (type) => {
        const iconMap = {
            click: MousePointerClick,
            wait: Clock,
            set_window: Target,
            image_recognition: FileSearch,
            branch: GitBranch,
            logic_check: SearchCheck,
            ocr_recognition: Binary,
            script_call: FileCode
        }
        return iconMap[type] || Target
    }

    const getImageUrl = (name) => {
        if (!name) return ''
        let cleanName = name.replace(/\\/g, '/')
        if (!/\.(png|jpg|jpeg)$/i.test(cleanName)) cleanName += '.png'
        return `/api/image/thumb?project_path=${encodeURIComponent(store.currentProjectPath || '')}&name=${encodeURIComponent(cleanName)}`
    }

    const onCardMouseDown = (e) => {
        emit('cardMouseDown', { event: e, taskId: props.task.task_id })
    }

    const onCardContextMenu = (e) => {
        emit('cardContextMenu', { event: e, task: props.task })
    }
</script>

<style scoped>
    .task-group-card {
        position: absolute;
        width: 280px;
        background: var(--el-bg-color);
        border: 1px solid var(--el-border-color-light);
        border-radius: var(--app-radius-md, 8px);
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
        user-select: none;
        cursor: move;
        z-index: 10;
        transition: border-color 0.2s, box-shadow 0.2s;
    }

        .task-group-card.is-current {
            border-color: var(--el-color-primary);
            box-shadow: 0 0 12px rgba(78, 209, 156, 0.25);
        }

    .task-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 12px;
        background: var(--el-fill-color-blank);
        border-bottom: 1px solid var(--el-border-color-light);
        border-radius: var(--app-radius-md, 8px) var(--app-radius-md, 8px) 0 0;
    }

    .task-title-area {
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .task-badge {
        font-size: 10px;
        background: var(--el-color-primary);
        color: #122118;
        padding: 1px 6px;
        border-radius: 4px;
        font-weight: 700;
    }

    .task-name {
        font-size: 13px;
        font-weight: 600;
        color: var(--el-text-color-primary);
    }

    .node-list {
        padding: 8px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        min-height: 80px;
    }

    .empty-node-tip {
        font-size: 11px;
        color: var(--el-text-color-placeholder);
        text-align: center;
        padding: 20px 0;
    }

    .node-card-item {
        position: relative;
        display: flex;
        flex-direction: column;
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: var(--app-radius-sm, 6px);
        padding: 8px;
        cursor: pointer;
        transition: all 0.2s;
    }

        .node-card-item:hover {
            border-color: var(--el-color-primary);
        }

        .node-card-item.is-selected {
            border-color: var(--el-color-primary);
            background: rgba(78, 209, 156, 0.12);
        }

        .node-card-item.is-disabled {
            opacity: 0.5;
            filter: grayscale(1);
        }

    .node-item-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
    }

    .node-header-left {
        display: flex;
        align-items: center;
        gap: 6px;
        overflow: hidden;
    }

    .node-type-icon {
        width: 14px;
        height: 14px;
        color: var(--el-color-primary);
        flex-shrink: 0;
    }

    .node-title {
        font-size: 12px;
        font-weight: 600;
        color: var(--el-text-color-primary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .node-index-badge {
        font-size: 10px;
        color: var(--el-text-color-secondary);
    }

    .node-body-image {
        margin-top: 6px;
        height: 60px;
        border-radius: 4px;
        overflow: hidden;
        background: #12131f;
        border: 1px solid var(--el-border-color-light);
    }

    .image-thumb-box {
        position: relative;
        width: 100%;
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
    }

        .image-thumb-box::before {
            content: '';
            position: absolute;
            inset: -10px;
            background-image: var(--bg-url);
            background-size: cover;
            filter: blur(10px) brightness(0.4);
        }

    .thumb-img {
        position: relative;
        max-width: 100%;
        max-height: 100%;
        object-fit: contain;
        z-index: 2;
    }

    .empty-thumb-box {
        height: 100%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 10px;
        color: var(--el-text-color-placeholder);
    }

    .node-item-footer {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 6px;
        font-size: 10px;
        color: var(--el-text-color-secondary);
    }

    .anchor {
        position: absolute;
        top: 50%;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: var(--el-color-primary);
        transform: translateY(-50%);
        opacity: 0;
        transition: opacity 0.2s;
        z-index: 5;
    }

    .node-card-item:hover .anchor {
        opacity: 1;
    }

    .anchor-in {
        left: -5px;
    }

    .anchor-out {
        right: -5px;
    }
</style>