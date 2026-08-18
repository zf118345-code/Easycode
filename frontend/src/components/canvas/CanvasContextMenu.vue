<!-- frontend/src/components/canvas/CanvasContextMenu.vue -->
<template>
    <!-- 节点类型选择菜单 -->
    <div
        v-if="spawnMenu.visible"
        class="spawn-menu"
        :style="{ left: spawnMenu.x + 'px', top: spawnMenu.y + 'px', zIndex: menuZIndex }"
        @mousedown.stop
        @click.stop>
        <div class="spawn-menu-header">
            {{ spawnMenu.sourceNodeId ? '快捷创建并连接' : '选择新建节点类型' }}
        </div>
        <div class="spawn-menu-list">
            <div
                v-for="(label, type) in availableNodeTypes"
                :key="type"
                class="spawn-menu-item"
                @click="$emit('create-and-connect', type)">
                {{ label }}
            </div>
        </div>
    </div>

    <!-- 画布右键菜单 -->
    <div
        v-if="contextMenu.visible"
        class="custom-context-menu"
        :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px', zIndex: menuZIndex }"
        @mousedown.stop
        @click.stop>
        <template v-if="contextMenu.targetType === 'node'">
            <template v-if="showDebugItems">
                <!-- 启动新运行的入口：会话活跃（运行中/已暂停）时隐藏，避免与「继续执行」冲突 -->
                <template v-if="!sessionActive">
                    <div class="menu-item" @click="$emit('run-from-node')">
                        <CirclePlay class="menu-item-icon" style="color: var(--el-color-primary);" />
                        <span>从此节点开始运行</span>
                    </div>
                    <div class="menu-divider" />
                    <div class="menu-item" @click="$emit('add-breakpoint-and-run', contextMenu.targetId)">
                        <span class="menu-item-icon">🎯</span>
                        <span>设断点并运行到此处</span>
                    </div>
                    <div class="menu-divider" />
                </template>
                <div class="menu-item" @click="$emit('toggle-breakpoint', contextMenu.targetId)">
                    <span class="menu-item-icon bp-dot-inline" />
                    <span>{{ hasBreakpoint ? '移除断点' : '设置断点' }}</span>
                </div>
                <template v-if="isPaused">
                    <div class="menu-divider" />
                    <div class="menu-item" @click="$emit('resume-execution')">继续执行 (F5)</div>
                    <div class="menu-item" @click="$emit('step-over')">单步跳过 (F10)</div>
                    <div class="menu-item danger" @click="$emit('stop-execution')">停止调试</div>
                </template>
            </template>
            <div class="menu-divider" />
            <div class="menu-item" @click="$emit('copy-node')">
                <Copy class="menu-item-icon" />
                <span>复制节点 (Ctrl+C)</span>
            </div>
            <div class="menu-divider" />
            <div class="menu-item danger" @click="$emit('delete-node')">
                <Trash2 class="menu-item-icon" />
                <span>删除节点</span>
            </div>
        </template>

        <template v-else-if="contextMenu.targetType === 'group'">
            <div class="menu-item danger" @click="$emit('delete-group')">
                <Trash2 class="menu-item-icon" />
                <span>删除组</span>
            </div>
        </template>

        <template v-else-if="contextMenu.targetType === 'canvas_in_group'">
            <div class="menu-item" @click="$emit('canvas-new-node')">
                在当前组 [{{ contextMenu.targetName }}] 新建节点
            </div>
            <div class="menu-item" @click="$emit('paste-node')">
                粘贴节点 (Ctrl+V)
            </div>
        </template>

        <template v-else-if="contextMenu.targetType === 'canvas_public'">
            <div class="menu-item" @click="$emit('canvas-new-node')">
                {{ hasGroups ? '在新建组中新建节点' : '新建节点' }}
            </div>
            <div class="menu-item" @click="$emit('paste-node')">
                粘贴节点 (Ctrl+V)
            </div>
        </template>

        <template v-else>
            <div class="menu-item" @click="$emit('canvas-new-node')">
                新建节点
            </div>
            <div class="menu-item" @click="$emit('paste-node')">
                粘贴节点 (Ctrl+V)
            </div>
        </template>
    </div>
</template>

<script setup>
    import { CirclePlay, Trash2, Copy } from 'lucide-vue-next'

    defineProps({
        spawnMenu: { type: Object, required: true },
        contextMenu: { type: Object, required: true },
        menuZIndex: { type: Number, default: 1000 },
        availableNodeTypes: { type: Object, default: () => ({}) },
        hasBreakpoint: { type: Boolean, default: false },
        isPaused: { type: Boolean, default: false },
        // 执行会话活跃（运行中/已暂停）：隐藏「从此节点开始运行 / 设断点并运行到此处」
        sessionActive: { type: Boolean, default: false },
        // 拓扑模式隐藏运行/断点/单步调试项与任务组项
        showDebugItems: { type: Boolean, default: true },
        hasGroups: { type: Boolean, default: true }
    })

    defineEmits([
        'create-and-connect',
        'run-from-node',
        'toggle-breakpoint',
        'add-breakpoint-and-run',
        'resume-execution',
        'step-over',
        'stop-execution',
        'copy-node',
        'paste-node',
        'delete-node',
        'delete-group',
        'canvas-new-node'
    ])
</script>
