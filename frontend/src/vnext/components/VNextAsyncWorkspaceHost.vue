<template>
    <component v-if="resolvedComponent" :is="resolvedComponent" v-bind="attrs" />
    <VNextWorkspaceState
        v-else
        :class="['async-workspace-state', attrs.class]"
        :style="attrs.style"
        :kind="errorMessage ? 'error' : 'loading'"
        :title="loading ? `正在打开${label}` : `${label}加载失败`"
        :description="errorMessage || '只在首次进入时加载，不影响当前项目内容。'"
        :aria-busy="loading ? 'true' : undefined"
    >
        <template #icon><LoaderCircle v-if="loading" :size="22" class="async-workspace-spinner" /><CircleAlert v-else :size="22" /></template>
        <template v-if="errorMessage" #actions><VNextButton size="compact" :disabled="loading" @click="loadWorkspace"><template #icon><RotateCcw aria-hidden="true" /></template>重新加载</VNextButton></template>
    </VNextWorkspaceState>
</template>

<script setup lang="ts">
import { CircleAlert, LoaderCircle, RotateCcw } from 'lucide-vue-next'
import { markRaw, onMounted, ref, useAttrs, type Component, type PropType } from 'vue'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'
import VNextButton from './ui/VNextButton.vue'

defineOptions({ inheritAttrs: false })

const props = defineProps({
    label: { type: String, required: true },
    loader: {
        type: Function as PropType<() => Promise<{ default: Component }>>,
        required: true,
    },
})

const attrs = useAttrs()
const componentCache = workspaceComponentCache
const resolvedComponent = ref<Component | null>(componentCache.get(props.label) || null)
const loading = ref(!resolvedComponent.value)
const errorMessage = ref('')
let requestId = 0

async function loadWorkspace() {
    const currentRequest = ++requestId
    loading.value = true
    errorMessage.value = ''
    try {
        const cached = componentCache.get(props.label)
        const component = cached || markRaw((await props.loader()).default)
        componentCache.set(props.label, component)
        if (currentRequest === requestId) resolvedComponent.value = component
    } catch (error) {
        if (currentRequest === requestId) {
            errorMessage.value = error instanceof Error ? error.message : '无法加载工作区，请重试。'
        }
    } finally {
        if (currentRequest === requestId) loading.value = false
    }
}

onMounted(() => {
    if (!resolvedComponent.value) void loadWorkspace()
})
</script>

<script lang="ts">
const workspaceComponentCache = new Map<string, import('vue').Component>()
</script>

<style scoped>
.async-workspace-state {
    min-width: 0;
    min-height: 0;
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 32px;
    background: var(--app-bg-base);
    color: var(--app-text-secondary);
    text-align: center;
}

.async-workspace-state > strong {
    color: var(--app-text-primary);
    font-size: var(--app-font-body);
}

.async-workspace-state > p {
    max-width: 520px;
    margin: 0;
    font-size: var(--app-font-caption);
    line-height: 1.6;
    overflow-wrap: anywhere;
}

.async-workspace-state > button {
    height: var(--app-control-compact);
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-top: 4px;
    padding: 0 10px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: var(--app-bg-input);
    color: var(--app-text-primary);
    cursor: pointer;
}

.async-workspace-state > button:hover,
.async-workspace-state > button:focus-visible {
    background: var(--app-bg-hover);
    box-shadow: var(--focus-ring);
}

.async-workspace-spinner {
    animation: async-workspace-spin .8s linear infinite;
}

@keyframes async-workspace-spin {
    to { transform: rotate(360deg); }
}
</style>
