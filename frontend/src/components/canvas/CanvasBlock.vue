<template>
    <section
        class="canvas-block"
        :class="[`tone-${block.color || 'orange'}`, { 'is-selected': selected, 'is-invalid': invalid }]"
        :style="blockStyle"
        :data-block-id="block.block_id"
        @mousedown.stop="emit('select', block.block_id)"
        @contextmenu.prevent.stop="emit('contextmenu', $event, block)">
        <header class="canvas-block-titlebar" @mousedown.stop="emit('drag-start', $event, block)">
            <GripHorizontal :size="14" aria-hidden="true" />
            <span class="canvas-block-name">{{ block.name }}</span>
            <span class="canvas-block-count">{{ containedCount }}</span>
            <button
                v-if="selected"
                type="button"
                class="canvas-block-delete"
                :aria-label="`删除区块 ${block.name}`"
                title="删除区块"
                @mousedown.stop
                @click.stop="emit('delete', block)">
                <Trash2 :size="13" />
            </button>
        </header>
        <p v-if="block.description" class="canvas-block-description">{{ block.description }}</p>
        <template v-if="selected">
            <i
                v-for="handle in handles"
                :key="handle"
                class="canvas-block-handle"
                :class="`handle-${handle}`"
                @mousedown.stop="emit('resize-start', $event, block, handle)" />
        </template>
    </section>
</template>

<script setup>
    import { computed } from 'vue'
    import { GripHorizontal, Trash2 } from 'lucide-vue-next'

    const props = defineProps({
        block: { type: Object, required: true },
        selected: { type: Boolean, default: false },
        invalid: { type: Boolean, default: false },
        containedCount: { type: Number, default: 0 }
    })
    const emit = defineEmits(['select', 'drag-start', 'resize-start', 'delete', 'contextmenu'])
    const handles = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
    const blockStyle = computed(() => ({
        left: `${props.block.x}px`,
        top: `${props.block.y}px`,
        width: `${props.block.width}px`,
        height: `${props.block.height}px`
    }))
</script>

<style scoped>
    .canvas-block {
        --block-accent: var(--app-color-primary, #d97732);
        position: absolute;
        box-sizing: border-box;
        border: 1px solid color-mix(in srgb, var(--block-accent) 28%, transparent);
        background: color-mix(in srgb, var(--block-accent) 4%, transparent);
        border-radius: 9px;
        z-index: 0;
        user-select: none;
        transition: border-color 120ms ease, background-color 120ms ease, box-shadow 120ms ease;
    }
    .canvas-block:hover,
    .canvas-block.is-selected {
        border-color: color-mix(in srgb, var(--block-accent) 65%, transparent);
        background: color-mix(in srgb, var(--block-accent) 7%, transparent);
    }
    .canvas-block.is-selected { box-shadow: 0 0 0 1px color-mix(in srgb, var(--block-accent) 20%, transparent); }
    .canvas-block.is-invalid { --block-accent: var(--el-color-danger, #e45d5d); }
    .tone-blue { --block-accent: #5f8fdf; }
    .tone-green { --block-accent: #5f9f7a; }
    .tone-purple { --block-accent: #9275cf; }
    .tone-gray { --block-accent: #8b8b84; }
    .canvas-block-titlebar {
        height: 32px;
        padding: 0 8px 0 10px;
        display: flex;
        align-items: center;
        gap: 7px;
        color: var(--app-text-secondary, #aaa79f);
        cursor: grab;
        font-size: 12px;
        font-weight: 650;
        letter-spacing: .01em;
    }
    .canvas-block-titlebar:active { cursor: grabbing; }
    .canvas-block-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .canvas-block-count {
        min-width: 18px;
        padding: 1px 5px;
        border-radius: 999px;
        color: var(--app-text-placeholder, #74736e);
        background: var(--app-bg-panel, #1c1c1a);
        font-size: 10px;
        text-align: center;
    }
    .canvas-block-delete {
        margin-left: auto;
        width: 24px;
        height: 24px;
        display: inline-grid;
        place-items: center;
        border: 0;
        border-radius: 5px;
        color: var(--app-text-placeholder, #77746d);
        background: transparent;
        cursor: pointer;
    }
    .canvas-block-delete:hover { color: var(--el-color-danger); background: color-mix(in srgb, var(--el-color-danger) 12%, transparent); }
    .canvas-block-description {
        position: absolute;
        left: 20px;
        top: 38px;
        max-width: calc(100% - 40px);
        margin: 0;
        color: var(--app-text-placeholder, #6e6c66);
        font-size: 10px;
        line-height: 1.4;
        pointer-events: none;
    }
    .canvas-block-handle { position: absolute; z-index: 2; }
    .handle-n, .handle-s { left: 12px; right: 12px; height: 8px; cursor: ns-resize; }
    .handle-n { top: -4px; } .handle-s { bottom: -4px; }
    .handle-e, .handle-w { top: 12px; bottom: 12px; width: 8px; cursor: ew-resize; }
    .handle-e { right: -4px; } .handle-w { left: -4px; }
    .handle-nw, .handle-ne, .handle-se, .handle-sw {
        width: 9px; height: 9px; border: 2px solid var(--app-bg-canvas, #11110f); border-radius: 50%; background: var(--block-accent);
    }
    .handle-nw { left: -5px; top: -5px; cursor: nwse-resize; }
    .handle-ne { right: -5px; top: -5px; cursor: nesw-resize; }
    .handle-se { right: -5px; bottom: -5px; cursor: nwse-resize; }
    .handle-sw { left: -5px; bottom: -5px; cursor: nesw-resize; }
</style>
