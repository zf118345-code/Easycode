<template>
    <div class="adb-picker" data-testid="adb-device-picker">
        <div class="adb-picker__header">
            <span>已连接设备</span>
            <button type="button" :disabled="disabled || loading || !store.workspace" @click="scan">
                <RefreshCw :size="13" :class="{ spinning: loading }" aria-hidden="true" />
                {{ scanned ? '重新扫描' : '扫描设备' }}
            </button>
        </div>
        <p v-if="!scanned" class="adb-picker__hint">扫描只提供候选项；选择后仍需保存，系统不会自动改绑。</p>
        <p v-else-if="message" :class="['adb-picker__message', { error: !available }]" :role="available ? 'status' : 'alert'">{{ message }}</p>
        <div v-if="scanned && candidates.length" class="adb-picker__list" role="listbox" aria-label="ADB 设备候选">
            <button
                v-for="candidate in candidates"
                :key="candidate.serial"
                type="button"
                role="option"
                :aria-selected="modelValue === candidate.serial"
                :disabled="disabled || !candidate.selectable"
                :class="{ selected: modelValue === candidate.serial }"
                @click="$emit('select', candidate.serial)"
            >
                <Smartphone :size="14" aria-hidden="true" />
                <span>
                    <strong>{{ candidate.display_name }}</strong>
                    <code>{{ candidate.serial }}</code>
                </span>
                <em :class="candidate.state">{{ stateLabel(candidate.state) }}</em>
            </button>
        </div>
    </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { RefreshCw, Smartphone } from 'lucide-vue-next'
import { vnextApi } from '../api'
import { useVNextStore } from '../store'
import type { AdbDeviceCandidate } from '../types'

defineProps<{ modelValue: string; disabled?: boolean }>()
defineEmits<{ select: [serial: string] }>()

const store = useVNextStore()
const loading = ref(false)
const scanned = ref(false)
const available = ref(true)
const message = ref('')
const candidates = ref<AdbDeviceCandidate[]>([])

async function scan(): Promise<void> {
    if (!store.workspace || loading.value) return
    loading.value = true
    message.value = ''
    try {
        const result = await vnextApi.adbCandidates(store.workspace)
        available.value = result.available
        candidates.value = result.candidates
        message.value = result.message || (result.candidates.length ? `发现 ${result.candidates.length} 个设备，请选择一个。` : '')
        scanned.value = true
    } catch (error) {
        available.value = false
        candidates.value = []
        message.value = error instanceof Error ? error.message : '无法扫描 ADB 设备。'
        scanned.value = true
    } finally {
        loading.value = false
    }
}

function stateLabel(state: string): string {
    if (state === 'device') return '可用'
    if (state === 'offline') return '离线'
    if (state === 'unauthorized') return '待授权'
    return state || '不可用'
}
</script>

<style scoped>
.adb-picker { margin-top: 2px; padding: 9px; border: 1px solid var(--app-border-subtle); border-radius: var(--app-radius-sm); background: color-mix(in srgb, var(--app-bg-input) 55%, transparent); }
.adb-picker__header { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.adb-picker__header > span { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.adb-picker__header button { min-height: 26px; display: inline-flex; align-items: center; gap: 5px; padding: 0 7px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-raised); color: var(--app-text-regular); font: inherit; font-size: var(--app-font-xs); cursor: pointer; }
.adb-picker__header button:hover:not(:disabled), .adb-picker__header button:focus-visible { border-color: var(--app-border-strong); background: var(--app-bg-hover); color: var(--app-text-primary); outline: 0; box-shadow: var(--focus-ring); }
.adb-picker__header button:disabled { opacity: .45; cursor: default; }
.spinning { animation: adb-spin .8s linear infinite; }
.adb-picker__hint, .adb-picker__message { margin: 7px 0 0; color: var(--app-text-placeholder); font-size: var(--app-font-xs); line-height: 1.45; }
.adb-picker__message.error { color: var(--app-color-danger); }
.adb-picker__list { display: flex; flex-direction: column; gap: 4px; margin-top: 8px; }
.adb-picker__list button { width: 100%; min-height: 42px; display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; align-items: center; gap: 6px; padding: 6px 7px; border: 1px solid transparent; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-regular); font: inherit; text-align: start; cursor: pointer; }
.adb-picker__list button:hover:not(:disabled), .adb-picker__list button:focus-visible { background: var(--app-bg-hover); outline: 0; box-shadow: var(--focus-ring); }
.adb-picker__list button.selected { border-color: var(--app-color-primary); background: var(--app-color-primary-dim); }
.adb-picker__list button:disabled { opacity: .58; cursor: default; }
.adb-picker__list span { min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.adb-picker__list strong, .adb-picker__list code { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.adb-picker__list strong { color: var(--app-text-primary); font-size: var(--app-font-xs); font-weight: 500; }
.adb-picker__list code { color: var(--app-text-secondary); font-size: var(--app-font-caption); }
.adb-picker__list em { color: var(--app-text-placeholder); font-size: var(--app-font-caption); font-style: normal; }
.adb-picker__list em.device { color: var(--app-color-success); }
.adb-picker__list em.unauthorized { color: var(--app-color-warning); }
@keyframes adb-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spinning { animation: none; } }
.adb-picker__list button { min-height: var(--app-list-row-rich); }
</style>
