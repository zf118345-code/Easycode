<template>
    <section class="problems-panel" :class="{ embedded }" aria-label="问题">
        <VNextPaneHeader v-if="!embedded" class="problems-header" title="问题" :meta="diagnostics.length">
            <template #actions><div class="problems-actions">
                <nav v-if="severityOptions.length > 1" aria-label="问题级别">
                    <button
                        v-for="option in severityOptions"
                        :key="option.value"
                        type="button"
                        :class="{ active: activeSeverity === option.value }"
                        :aria-pressed="activeSeverity === option.value"
                        @click="activeSeverity = option.value"
                    >{{ option.label }} <span>{{ option.count }}</span></button>
                </nav>
                <VNextIconButton class="close-button" label="关闭问题面板" @click="emit('close')"><X aria-hidden="true" /></VNextIconButton>
            </div></template>
        </VNextPaneHeader>

        <div class="problem-list" role="list">
            <button
                v-for="(diagnostic, index) in filteredDiagnostics"
                :key="diagnosticKey(diagnostic, index)"
                type="button"
                role="listitem"
                class="problem-row"
                :data-severity="severity(diagnostic)"
                @click="emit('open', diagnostic)"
            >
                <CircleX v-if="severity(diagnostic) === 'error'" :size="14" aria-hidden="true" />
                <TriangleAlert v-else-if="severity(diagnostic) === 'warning'" :size="14" aria-hidden="true" />
                <Info v-else :size="14" aria-hidden="true" />
                <span class="problem-message">{{ diagnostic.message }}</span>
                <span class="problem-location">{{ locationLabel(diagnostic) }}</span>
                <code>{{ diagnostic.code }}</code>
            </button>
            <VNextWorkspaceState v-if="!filteredDiagnostics.length" class="problems-empty" compact :kind="diagnostics.length ? 'filtered' : 'empty'" :title="diagnostics.length ? '当前级别没有问题' : '当前项目函数没有已知问题'"><template #icon><CircleCheck :size="20" /></template></VNextWorkspaceState>
        </div>
    </section>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CircleCheck, CircleX, Info, TriangleAlert, X } from 'lucide-vue-next'
import type { ProgramDiagnosticDto, ProgramSummaryDto } from './serverTypes'
import VNextPaneHeader from '../components/ui/VNextPaneHeader.vue'
import VNextWorkspaceState from '../components/ui/VNextWorkspaceState.vue'
import VNextIconButton from '../components/ui/VNextIconButton.vue'

const props = withDefaults(defineProps<{
    diagnostics?: ProgramDiagnosticDto[]
    programs?: ProgramSummaryDto[]
    embedded?: boolean
}>(), { diagnostics: () => [], programs: () => [], embedded: false })
const emit = defineEmits<{ close: []; open: [diagnostic: ProgramDiagnosticDto] }>()
const activeSeverity = ref('all')

function severity(diagnostic: ProgramDiagnosticDto): 'error' | 'warning' | 'info' {
    if (diagnostic.severity === 'error') return 'error'
    if (diagnostic.severity === 'warning') return 'warning'
    return 'info'
}

const severityOptions = computed(() => {
    const counts = { error: 0, warning: 0, info: 0 }
    for (const diagnostic of props.diagnostics) counts[severity(diagnostic)] += 1
    return [
        { value: 'all', label: '全部', count: props.diagnostics.length },
        ...(['error', 'warning', 'info'] as const)
            .filter((value) => counts[value] > 0)
            .map((value) => ({
                value,
                label: value === 'error' ? '错误' : value === 'warning' ? '警告' : '提示',
                count: counts[value],
            })),
    ]
})
const filteredDiagnostics = computed(() => activeSeverity.value === 'all'
    ? props.diagnostics
    : props.diagnostics.filter((diagnostic) => severity(diagnostic) === activeSeverity.value))

watch(severityOptions, (options) => {
    if (!options.some((item) => item.value === activeSeverity.value)) activeSeverity.value = 'all'
})

function diagnosticKey(diagnostic: ProgramDiagnosticDto, index: number): string {
    return [diagnostic.code, diagnostic.function_id, diagnostic.statement_id, diagnostic.value_id, index].filter(Boolean).join(':')
}

function locationLabel(diagnostic: ProgramDiagnosticDto): string {
    const program = props.programs.find((item) => item.function_id === diagnostic.function_id)
    const labels = [program?.display_name]
    if (diagnostic.field_path) labels.push(diagnostic.field_path)
    else if (diagnostic.value_id) labels.push('参数值')
    else if (diagnostic.statement_id) labels.push('语句')
    return labels.filter(Boolean).join(' · ') || '项目'
}
</script>

<style scoped>
.problems-panel { min-height: 150px; height: min(270px, 36vh); display: grid; grid-template-rows: 38px minmax(0, 1fr); border-top: 1px solid var(--app-border-default); background: var(--app-bg-panel); color: var(--app-text-regular); }
.problems-panel.embedded { width: 100%; height: 100%; min-height: 0; grid-template-rows: minmax(0, 1fr); border-top: 0; }
.problems-header, .problems-title, .problems-actions, .problems-actions nav { display: flex; align-items: center; }
.problems-header { justify-content: space-between; gap: var(--app-spacing-md); padding: 0 var(--app-spacing-sm) 0 var(--app-spacing-md); border-bottom: 1px solid var(--app-border-subtle); }
.problems-title { gap: var(--app-spacing-sm); min-width: 0; }
.problems-title > svg { color: var(--app-text-secondary); }
.problems-title strong { color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; }
.problems-title span { color: var(--app-text-placeholder); font-size: var(--app-font-xs); font-variant-numeric: tabular-nums; }
.problems-actions { gap: var(--app-spacing-sm); min-width: 0; }
.problems-actions nav { gap: 2px; }
.problems-actions button { min-height: var(--app-control-compact); padding: 0 var(--app-spacing-sm); border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); font: inherit; font-size: var(--app-font-xs); cursor: pointer; }
.problems-actions button:hover, .problems-actions button:focus-visible, .problems-actions button.active { background: var(--app-bg-hover); color: var(--app-text-primary); outline: 0; }
.problems-actions button:focus-visible { box-shadow: var(--focus-ring); }
.problems-actions button span { color: var(--app-text-placeholder); font-variant-numeric: tabular-nums; }
.problems-actions .close-button { width: var(--app-control-compact); padding: 0; }
.problem-list { min-height: 0; overflow: auto; }
.problem-row { width: 100%; min-height: var(--app-control-default); display: grid; grid-template-columns: 18px minmax(0, 1fr) minmax(120px, .34fr) auto; align-items: center; gap: var(--app-spacing-sm); padding: 5px var(--app-spacing-md); border: 0; border-bottom: 1px solid var(--app-border-subtle); background: transparent; color: var(--app-text-regular); font: inherit; font-size: var(--app-font-xs); text-align: start; cursor: pointer; }
.problem-row:hover { background: var(--app-bg-hover); }
.problem-row:focus-visible { outline: 0; box-shadow: inset 0 0 0 2px var(--app-color-primary); }
.problem-row[data-severity='error'] > svg { color: var(--app-color-danger); }
.problem-row[data-severity='warning'] > svg { color: var(--app-color-warning); }
.problem-row[data-severity='info'] > svg { color: var(--app-color-info); }
.problem-message, .problem-location { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.problem-location { color: var(--app-text-secondary); }
.problem-row code { color: var(--app-text-placeholder); font-family: var(--app-font-mono); font-size: var(--app-font-xs); }
.problems-empty { height: 100%; min-height: 110px; display: flex; align-items: center; justify-content: center; gap: var(--app-spacing-sm); color: var(--app-text-secondary); font-size: var(--app-font-sm); }
.problems-empty > svg { color: var(--app-color-success); }
@media (max-width: 820px) { .problem-row { grid-template-columns: 18px minmax(0, 1fr) auto; } .problem-location { display: none; } .problems-actions nav { display: none; } }
</style>
