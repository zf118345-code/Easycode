<template>
    <div ref="root" class="vnext-overflow-tabs">
        <div ref="measurement" class="vnext-overflow-tabs__measurement" aria-hidden="true">
            <span v-for="item in items" :key="item.id">{{ item.label }}</span><span>更多页面</span>
        </div>
        <div class="vnext-overflow-tabs__list" role="tablist" :aria-label="label" @keydown="handleKeydown">
            <button
                v-for="item in visibleItems"
                :key="item.id"
                type="button"
                role="tab"
                :aria-selected="item.id === modelValue"
                :tabindex="item.id === modelValue ? 0 : -1"
                :class="{ active: item.id === modelValue }"
                @click="select(item.id)"
            >{{ item.label }}</button>
            <details v-if="hiddenItems.length" ref="overflowMenu" class="vnext-overflow-tabs__more">
                <summary :class="{ active: hiddenItems.some((item) => item.id === modelValue) }">
                    <MoreHorizontal :size="14" /><span>更多页面</span>
                </summary>
                <div role="menu">
                    <button
                        v-for="item in hiddenItems"
                        :key="item.id"
                        type="button"
                        role="menuitemradio"
                        :aria-checked="item.id === modelValue"
                        :class="{ active: item.id === modelValue }"
                        @click="select(item.id)"
                    >{{ item.label }}</button>
                </div>
            </details>
        </div>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { MoreHorizontal } from 'lucide-vue-next'

export interface OverflowTabItem { id: string; label: string }

const props = withDefaults(defineProps<{
    items: OverflowTabItem[]
    modelValue: string
    label?: string
}>(), { label: '页面' })
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const root = ref<HTMLElement | null>(null)
const measurement = ref<HTMLElement | null>(null)
const overflowMenu = ref<HTMLDetailsElement | null>(null)
const visibleIds = ref<string[]>([])
let observer: ResizeObserver | null = null

const visibleItems = computed(() => visibleIds.value
    .map((id) => props.items.find((item) => item.id === id))
    .filter((item): item is OverflowTabItem => Boolean(item)))
const hiddenItems = computed(() => props.items.filter((item) => !visibleIds.value.includes(item.id)))

function recalculate() {
    const width = root.value?.clientWidth || 0
    const nodes = Array.from(measurement.value?.children || []) as HTMLElement[]
    if (!width || nodes.length < props.items.length + 1) {
        visibleIds.value = props.items.map((item) => item.id)
        return
    }
    const widths = nodes.slice(0, props.items.length).map((node, index) =>
        Math.min(190, Math.max(node.getBoundingClientRect().width, props.items[index].label.length * 14 + 30)))
    const total = widths.reduce((sum, item) => sum + item, 0)
    if (total <= width) {
        visibleIds.value = props.items.map((item) => item.id)
        return
    }
    const moreWidth = Math.max(nodes[nodes.length - 1].getBoundingClientRect().width, 86)
    const available = Math.max(0, width - moreWidth)
    const visible: string[] = []
    let used = 0
    for (let index = 0; index < props.items.length; index += 1) {
        if (visible.length && used + widths[index] > available) break
        visible.push(props.items[index].id)
        used += widths[index]
    }
    if (!visible.length && props.items.length) visible.push(props.items[0].id)
    if (props.modelValue && !visible.includes(props.modelValue)) {
        visible[Math.max(0, visible.length - 1)] = props.modelValue
        visible.sort((left, right) => props.items.findIndex((item) => item.id === left) - props.items.findIndex((item) => item.id === right))
    }
    visibleIds.value = [...new Set(visible)]
}

function select(id: string) {
    emit('update:modelValue', id)
    if (overflowMenu.value) overflowMenu.value.open = false
    void nextTick(recalculate)
}

function handleKeydown(event: KeyboardEvent) {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key) || !props.items.length) return
    event.preventDefault()
    const current = Math.max(0, props.items.findIndex((item) => item.id === props.modelValue))
    const next = event.key === 'Home' ? 0
        : event.key === 'End' ? props.items.length - 1
          : event.key === 'ArrowLeft' ? (current - 1 + props.items.length) % props.items.length
            : (current + 1) % props.items.length
    select(props.items[next].id)
    void nextTick(() => root.value?.querySelector<HTMLElement>(`[role="tab"][aria-selected="true"]`)?.focus())
}

function closeOutside(event: PointerEvent) {
    if (overflowMenu.value?.open && !overflowMenu.value.contains(event.target as Node)) overflowMenu.value.open = false
}

watch(() => [props.modelValue, ...props.items.flatMap((item) => [item.id, item.label])], () => void nextTick(recalculate))
onMounted(() => {
    visibleIds.value = props.items.map((item) => item.id)
    if (typeof ResizeObserver !== 'undefined') {
        observer = new ResizeObserver(recalculate)
        if (root.value) observer.observe(root.value)
    }
    document.addEventListener('pointerdown', closeOutside)
    void nextTick(recalculate)
})
onBeforeUnmount(() => {
    observer?.disconnect()
    document.removeEventListener('pointerdown', closeOutside)
})
</script>

<style scoped>
.vnext-overflow-tabs{position:relative;min-width:0;overflow:visible;border-bottom:1px solid var(--app-border-subtle);background:var(--app-bg-sidebar)}
.vnext-overflow-tabs__measurement{position:absolute;left:-10000px;top:-10000px;display:flex;visibility:hidden;pointer-events:none}
.vnext-overflow-tabs__measurement span,.vnext-overflow-tabs__list>button,.vnext-overflow-tabs__more>summary{box-sizing:border-box;height:var(--app-control-default);padding:0 13px;font:inherit;font-size:var(--app-font-interface);font-weight:600;white-space:nowrap}
.vnext-overflow-tabs__list{min-width:0;height:calc(var(--app-control-default) + 10px);display:flex;align-items:end;padding:5px 10px 0;overflow:visible}
.vnext-overflow-tabs__list>button{position:relative;max-width:190px;overflow:hidden;border:0;background:transparent;color:var(--app-text-secondary);text-overflow:ellipsis;cursor:pointer}
.vnext-overflow-tabs__list>button::after,.vnext-overflow-tabs__more>summary::after{content:"";position:absolute;right:9px;bottom:0;left:9px;height:2px;border-radius:2px 2px 0 0;background:transparent}
.vnext-overflow-tabs__list>button:hover,.vnext-overflow-tabs__list>button.active{color:var(--app-text-primary);background:var(--app-bg-hover)}
.vnext-overflow-tabs__list>button.active::after,.vnext-overflow-tabs__more>summary.active::after{background:var(--app-color-primary)}
.vnext-overflow-tabs__list>button:focus-visible,.vnext-overflow-tabs__more>summary:focus-visible{outline:0;box-shadow:inset var(--focus-ring)}
.vnext-overflow-tabs__more{position:relative;margin-left:auto}
.vnext-overflow-tabs__more>summary{position:relative;display:flex;align-items:center;gap:6px;list-style:none;color:var(--app-text-secondary);cursor:pointer}
.vnext-overflow-tabs__more>summary::-webkit-details-marker{display:none}
.vnext-overflow-tabs__more>summary:hover,.vnext-overflow-tabs__more>summary.active{background:var(--app-bg-hover);color:var(--app-text-primary)}
.vnext-overflow-tabs__more>div{position:absolute;z-index:30;top:calc(100% + 5px);right:0;min-width:180px;max-width:min(280px,calc(100vw - 24px));max-height:300px;overflow:auto;padding:5px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-md);background:var(--app-bg-overlay);box-shadow:var(--app-shadow-overlay)}
.vnext-overflow-tabs__more>div button{width:100%;height:var(--app-control-default);display:block;overflow:hidden;padding:0 10px;border:0;border-radius:var(--app-radius-sm);background:transparent;color:var(--app-text-secondary);font:inherit;text-align:left;text-overflow:ellipsis;white-space:nowrap;cursor:pointer}
.vnext-overflow-tabs__more>div button:hover,.vnext-overflow-tabs__more>div button.active{background:var(--app-bg-hover);color:var(--app-text-primary)}
@media(max-width:760px){.vnext-overflow-tabs{position:sticky;top:0;z-index:4}.vnext-overflow-tabs__list{height:48px;padding:5px 8px 0}.vnext-overflow-tabs__measurement span,.vnext-overflow-tabs__list>button,.vnext-overflow-tabs__more>summary{height:42px}}
</style>
