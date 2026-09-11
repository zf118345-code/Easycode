<template>
    <section class="feedback-panel" aria-label="运行与检查">
        <VNextPaneHeader title="运行与检查" :meta="statusLabel">
            <template #actions>
                <nav class="feedback-tabs" aria-label="反馈内容">
                    <button v-for="item in tabs" :key="item.id" type="button" :class="{ active: activeTab === item.id }" :aria-pressed="activeTab === item.id" @click="emit('update:activeTab', item.id)">
                        {{ item.label }}<span v-if="item.count !== undefined">{{ item.count }}</span>
                    </button>
                </nav>
                <VNextIconButton class="close-button" label="关闭底部面板" @click="emit('close')"><X aria-hidden="true" /></VNextIconButton>
            </template>
        </VNextPaneHeader>
        <ProgramRunConsole v-if="activeTab !== 'problems'" embedded :mode="activeTab" :session="session" @locate-statement="emit('locateStatement', $event)" />
        <ProgramProblemsPanel v-else embedded :diagnostics="diagnostics" :programs="programs" @open="emit('openProblem', $event)" />
    </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { X } from 'lucide-vue-next'
import type { RuntimeSession } from '../types'
import type { ProgramDiagnosticDto, ProgramSummaryDto } from './serverTypes'
import ProgramProblemsPanel from './ProgramProblemsPanel.vue'
import ProgramRunConsole from './ProgramRunConsole.vue'
import VNextPaneHeader from '../components/ui/VNextPaneHeader.vue'
import VNextIconButton from '../components/ui/VNextIconButton.vue'

export type BottomFeedbackTab = 'output' | 'values' | 'problems'

const props = defineProps<{
    activeTab: BottomFeedbackTab
    session: RuntimeSession | null
    diagnostics: ProgramDiagnosticDto[]
    programs: ProgramSummaryDto[]
}>()

const emit = defineEmits<{
    'update:activeTab': [tab: BottomFeedbackTab]
    close: []
    locateStatement: [statementId: string]
    openProblem: [diagnostic: ProgramDiagnosticDto]
}>()

const valueCount = computed(() => (props.session?.value_entries?.local.length || 0) + (props.session?.value_entries?.project.length || 0))
const tabs = computed(() => [
    { id: 'output' as const, label: '输出', count: props.session?.events.length || 0 },
    { id: 'values' as const, label: '当前值', count: valueCount.value },
    { id: 'problems' as const, label: '问题', count: props.diagnostics.length },
])
const statusLabel = computed(() => {
    const status = props.session?.status
    if (status === 'queued') return '准备中'
    if (status === 'running') return '运行中'
    if (status === 'paused') return '已暂停'
    if (status === 'completed') return '已完成'
    if (status === 'failed') return '失败'
    if (status === 'cancelled') return '已停止'
    return ''
})
</script>

<style scoped>
.feedback-panel { height: 100%; min-height: 0; display: grid; grid-template-rows: var(--app-height-pane-header) minmax(0, 1fr); overflow: hidden; background: var(--app-bg-sidebar); color: var(--app-text-regular); }
.feedback-tabs { display: flex; align-items: center; gap: 2px; }
.feedback-tabs button { height: var(--app-control-compact); display: inline-flex; align-items: center; gap: 5px; padding: 0 9px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); font: inherit; font-size: var(--app-font-xs); cursor: pointer; }
.feedback-tabs button:hover, .feedback-tabs button:focus-visible { outline: 0; background: var(--app-bg-hover); color: var(--app-text-primary); }
.feedback-tabs button.active { background: var(--app-bg-active); color: var(--app-text-primary); }
.feedback-tabs span { color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.close-button { width: var(--app-control-compact); height: var(--app-control-compact); display: grid; place-items: center; padding: 0; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); cursor: pointer; }
.close-button:hover, .close-button:focus-visible { outline: 0; background: var(--app-bg-hover); color: var(--app-text-primary); }
</style>
