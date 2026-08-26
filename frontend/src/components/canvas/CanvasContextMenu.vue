<!-- frontend/src/components/canvas/CanvasContextMenu.vue -->
<template>
    <!-- 节点类型选择菜单 -->
    <div
        v-if="spawnMenu.visible"
        ref="spawnMenuRef"
        class="spawn-menu"
        role="menu"
        aria-label="新建节点"
        :style="{ left: spawnMenu.x + 'px', top: spawnMenu.y + 'px', zIndex: menuZIndex }"
        @mousedown.stop
        @click.stop
        @keydown="handleMenuKeydown">
        <div class="spawn-menu-header">
            {{ spawnMenu.sourceNodeId ? '快捷创建并连接' : '选择新建节点类型' }}
        </div>
        <div class="spawn-menu-list">
            <button
                v-for="(label, type) in availableNodeTypes"
                :key="type"
                type="button"
                role="menuitem"
                class="spawn-menu-item"
                @click="$emit('create-and-connect', type)">
                {{ label }}
            </button>
        </div>
    </div>

    <!-- 画布右键菜单 -->
    <div
        v-if="contextMenu.visible"
        ref="contextMenuRef"
        class="custom-context-menu"
        role="menu"
        aria-label="画布操作"
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px', zIndex: menuZIndex }"
        @mousedown.stop
        @click.stop
        @keydown="handleMenuKeydown">
        <template v-if="contextMenu.targetType === 'node'">
            <template v-if="showDebugItems">
                <!-- 启动新运行的入口：会话活跃（运行中/已暂停）时隐藏，避免与「继续执行」冲突 -->
                <template v-if="!sessionActive">
                    <button type="button" role="menuitem" class="menu-item" :disabled="runDisabled" @click="$emit('run-from-node')">
                        <CirclePlay class="menu-item-icon" style="color: var(--el-color-primary);" />
                        <span>从当前节点执行</span>
                    </button>
                    <div class="menu-divider" role="separator" />
                </template>
                <button type="button" role="menuitem" class="menu-item" @click="$emit('toggle-breakpoint', contextMenu.targetId)">
                    <span class="menu-item-icon bp-dot-inline" />
                    <span>{{ hasBreakpoint ? '移除断点' : '设置断点' }}</span>
                </button>
                <template v-if="isPaused">
                    <div class="menu-divider" role="separator" />
                    <button type="button" role="menuitem" class="menu-item" @click="$emit('resume-execution')">继续执行 (F5)</button>
                    <button type="button" role="menuitem" class="menu-item" @click="$emit('step-over')">单步跳过 (F10)</button>
                    <button type="button" role="menuitem" class="menu-item danger" @click="$emit('stop-execution')">停止调试</button>
                </template>
            </template>
            <div class="menu-divider" role="separator" />
            <button type="button" role="menuitem" class="menu-item" @click="$emit('copy-node')">
                <Copy class="menu-item-icon" />
                <span>复制节点 (Ctrl+C)</span>
            </button>
            <div class="menu-divider" role="separator" />
            <button type="button" role="menuitem" class="menu-item danger" @click="$emit('delete-node')">
                <Trash2 class="menu-item-icon" />
                <span>删除节点</span>
            </button>
        </template>

        <template v-else-if="contextMenu.targetType === 'block'">
            <button type="button" role="menuitem" class="menu-item danger" @click="$emit('delete-block')">
                <Trash2 class="menu-item-icon" />
                <span>删除区块</span>
            </button>
        </template>

        <template v-else-if="contextMenu.targetType === 'edge'">
            <button type="button" role="menuitem" class="menu-item" @click="$emit('add-waypoint')">
                <Route class="menu-item-icon" />
                <span>添加转接点</span>
            </button>
            <button type="button" role="menuitem" class="menu-item" @click="$emit('reset-edge-routing')">
                <RotateCcw class="menu-item-icon" />
                <span>重置自动路由</span>
            </button>
        </template>

        <template v-else-if="contextMenu.targetType === 'canvas_public'">
            <button type="button" role="menuitem" class="menu-item" @click="$emit('canvas-new-node')">
                <CirclePlus class="menu-item-icon" />
                <span>新建节点</span>
            </button>
            <button type="button" role="menuitem" class="menu-item" @click="$emit('canvas-new-block')">
                <PanelsTopLeft class="menu-item-icon" />
                <span>新建区块</span>
            </button>
            <button type="button" role="menuitem" class="menu-item" :disabled="!hasClipboard" @click="$emit('paste-node')">
                <ClipboardPaste class="menu-item-icon" />
                <span>粘贴节点 (Ctrl+V)</span>
            </button>
        </template>

        <template v-else>
            <button type="button" role="menuitem" class="menu-item" @click="$emit('canvas-new-node')">
                新建节点
            </button>
            <button type="button" role="menuitem" class="menu-item" :disabled="!hasClipboard" @click="$emit('paste-node')">
                粘贴节点 (Ctrl+V)
            </button>
        </template>
    </div>
</template>

<script setup>
    import { nextTick, ref, watch } from 'vue'
    import { CirclePlay, Trash2, Copy, CirclePlus, PanelsTopLeft, ClipboardPaste, Route, RotateCcw } from 'lucide-vue-next'

    const props = defineProps({
        spawnMenu: { type: Object, required: true },
        contextMenu: { type: Object, required: true },
        menuZIndex: { type: Number, default: 1000 },
        availableNodeTypes: { type: Object, default: () => ({}) },
        hasBreakpoint: { type: Boolean, default: false },
        isPaused: { type: Boolean, default: false },
        // 执行会话活跃（运行中/已暂停）：隐藏「从此节点开始运行 / 设断点并运行到此处」
        sessionActive: { type: Boolean, default: false },
// 拓扑模式隐藏运行、断点与单步调试项。
        showDebugItems: { type: Boolean, default: true },
        hasClipboard: { type: Boolean, default: false },
        runDisabled: { type: Boolean, default: false }
    })

    const emit = defineEmits([
        'create-and-connect',
        'run-from-node',
        'toggle-breakpoint',
        'resume-execution',
        'step-over',
        'stop-execution',
        'copy-node',
        'paste-node',
        'delete-node',
        'delete-block',
        'add-waypoint',
        'reset-edge-routing',
        'canvas-new-node',
        'canvas-new-block',
        'dismiss'
    ])

    const spawnMenuRef = ref(null)
    const contextMenuRef = ref(null)

    const focusFirstItem = async rootRef => {
        await nextTick()
        rootRef.value?.querySelector('button:not(:disabled)')?.focus({ preventScroll: true })
    }

    watch(() => props.spawnMenu.visible, visible => { if (visible) focusFirstItem(spawnMenuRef) })
    watch(() => props.contextMenu.visible, visible => { if (visible) focusFirstItem(contextMenuRef) })

    const handleMenuKeydown = event => {
        if (event.key === 'Escape') {
            event.preventDefault()
            emit('dismiss')
            return
        }
        if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
        const items = [...event.currentTarget.querySelectorAll('button:not(:disabled)')]
        if (!items.length) return
        event.preventDefault()
        const currentIndex = Math.max(0, items.indexOf(document.activeElement))
        const nextIndex = event.key === 'Home'
            ? 0
            : event.key === 'End'
                ? items.length - 1
                : (currentIndex + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length
        items[nextIndex]?.focus({ preventScroll: true })
    }
</script>

<style scoped>
    .menu-item:disabled {
        opacity: 0.42;
        cursor: not-allowed;
    }
</style>
