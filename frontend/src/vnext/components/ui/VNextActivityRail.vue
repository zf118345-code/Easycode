<template>
    <aside class="vnext-activity-rail" :class="`is-${mode}`" :aria-label="ariaLabel">
        <template v-for="item in topItems" :key="item.id">
            <span v-if="item.dividerBefore" class="vnext-activity-rail__divider" aria-hidden="true" />
            <button
                type="button"
                :class="{ active: item.active }"
                :aria-label="item.ariaLabel || item.label"
                :title="item.title || item.ariaLabel || item.label"
                :aria-current="item.current ? 'page' : undefined"
                :aria-expanded="item.expanded"
                @click="emit('activate', item.id)"
            >
                <component :is="item.icon" :size="19" aria-hidden="true" />
                <span class="vnext-activity-rail__label">{{ item.label }}</span>
                <span v-if="item.badge" class="vnext-activity-rail__badge">{{ item.badge }}</span>
            </button>
        </template>
        <span class="vnext-activity-rail__spacer" aria-hidden="true" />
        <template v-for="item in bottomItems" :key="item.id">
            <span v-if="item.dividerBefore" class="vnext-activity-rail__divider" aria-hidden="true" />
            <button
                type="button"
                :class="{ active: item.active }"
                :aria-label="item.ariaLabel || item.label"
                :title="item.title || item.ariaLabel || item.label"
                @click="emit('activate', item.id)"
            >
                <component :is="item.icon" :size="19" aria-hidden="true" />
                <span class="vnext-activity-rail__label">{{ item.label }}</span>
                <span v-if="item.badge" class="vnext-activity-rail__badge">{{ item.badge }}</span>
            </button>
        </template>
    </aside>
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue'

export type ActivityRailMode = 'compact' | 'labeled'

export interface ActivityRailItem {
    id: string
    label: string
    icon: Component
    active?: boolean
    current?: boolean
    expanded?: boolean
    ariaLabel?: string
    title?: string
    badge?: string | number
    dividerBefore?: boolean
    placement?: 'top' | 'bottom'
}

const props = withDefaults(defineProps<{
    items: ActivityRailItem[]
    mode?: ActivityRailMode
    ariaLabel?: string
}>(), { mode: 'labeled', ariaLabel: '工作区' })

const emit = defineEmits<{ activate: [id: string] }>()
const topItems = computed(() => props.items.filter(item => item.placement !== 'bottom'))
const bottomItems = computed(() => props.items.filter(item => item.placement === 'bottom'))
</script>

<style scoped>
.vnext-activity-rail {
    width: 44px;
    flex: 0 0 44px;
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 4px;
    padding: 6px 5px;
    overflow: hidden;
    border-right: 1px solid var(--app-border-subtle);
    background: var(--app-bg-chrome);
}

.vnext-activity-rail.is-labeled { width: 132px; flex-basis: 132px; }
.vnext-activity-rail button {
    position: relative;
    width: 100%;
    height: var(--app-control-default);
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 0 7px;
    overflow: hidden;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    font: inherit;
    text-align: left;
    cursor: pointer;
}
.vnext-activity-rail button > svg { flex: 0 0 19px; }
.vnext-activity-rail button:hover,
.vnext-activity-rail button:focus-visible { outline: 0; background: var(--app-bg-hover); color: var(--app-text-primary); }
.vnext-activity-rail button:focus-visible { box-shadow: var(--focus-ring); }
.vnext-activity-rail button.active { background: color-mix(in srgb, var(--app-color-primary) 11%, transparent); color: var(--app-color-primary-hover); }
.vnext-activity-rail button.active::before { content: ''; position: absolute; left: 0; width: 2px; height: 18px; background: var(--app-color-primary-hover); }
.vnext-activity-rail__label { min-width: 0; overflow: hidden; font-size: var(--app-font-xs); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.is-compact .vnext-activity-rail__label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
.vnext-activity-rail__divider { width: calc(100% - 12px); height: 1px; flex: 0 0 1px; margin: 2px 6px; background: var(--app-border-subtle); }
.vnext-activity-rail__spacer { flex: 1; }
.vnext-activity-rail__badge { min-width: 15px; height: 15px; display: grid; place-items: center; margin-left: auto; padding: 0 3px; border-radius: 8px; background: var(--app-color-danger); color: var(--app-color-on-primary); font-size: var(--app-font-caption); }
.is-compact .vnext-activity-rail__badge { position: absolute; right: 0; bottom: 0; border: 1px solid var(--app-bg-chrome); }

@media (max-width: 1099px) {
    .vnext-activity-rail.is-labeled { width: 44px; flex-basis: 44px; }
    .vnext-activity-rail.is-labeled .vnext-activity-rail__label { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
    .vnext-activity-rail.is-labeled .vnext-activity-rail__badge { position: absolute; right: 0; bottom: 0; border: 1px solid var(--app-bg-chrome); }
}

</style>
