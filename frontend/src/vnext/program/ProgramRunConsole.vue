<template>
    <section
        class="run-console"
        :class="{
            embedded,
            'values-only': embedded && activeMode === 'values',
            'without-footer': embedded && activeMode === 'log' && !session,
        }"
        :aria-label="activeMode === 'values' ? '当前值' : '运行输出'"
    >
        <header v-if="!embedded || activeMode === 'log'" class="console-header" :class="{ embedded }">
            <div v-if="!embedded" class="console-title">
                <TerminalSquare :size="15" aria-hidden="true" />
                <strong>运行与调试</strong>
                <span v-if="session" class="status-pill" :data-status="session.status">{{ statusLabel }}</span>
            </div>

            <div v-if="session && !embedded" class="console-mode-tabs" aria-label="运行信息">
                <button type="button" :class="{ active: activeMode === 'log' }" @click="activeMode = 'log'">日志</button>
                <button type="button" :class="{ active: activeMode === 'values' }" @click="activeMode = 'values'">
                    当前值 <span>{{ valueCount }}</span>
                </button>
            </div>

            <div class="console-actions">
                <button
                    type="button"
                    :class="{ active: autoScroll }"
                    :aria-pressed="autoScroll"
                    title="自动跟随最新日志"
                    aria-label="自动跟随最新日志"
                    @click="autoScroll = !autoScroll"
                >
                    <ArrowDownToLine :size="14" aria-hidden="true" />
                </button>
                <button
                    type="button"
                    title="清空当前视图（不会删除诊断日志）"
                    aria-label="清空当前视图，不删除诊断日志"
                    :disabled="!visibleEvents.length"
                    @click="clearView"
                >
                    <Eraser :size="14" aria-hidden="true" />
                </button>
                <button v-if="!embedded" type="button" title="关闭日志" aria-label="关闭日志" @click="emit('close')">
                    <X :size="14" aria-hidden="true" />
                </button>
            </div>
        </header>

        <nav v-if="activeMode === 'log' && categories.length > 1" class="category-tabs" aria-label="日志分类">
            <button
                v-for="item in categories"
                :key="item.value"
                type="button"
                :class="{ active: activeCategory === item.value }"
                :aria-pressed="activeCategory === item.value"
                @click="activeCategory = item.value"
            >
                {{ item.label }}
                <span>{{ item.count }}</span>
            </button>
        </nav>

        <div v-if="activeMode === 'log'" ref="eventList" class="event-list" role="log" aria-live="polite" aria-relevant="additions text">
            <div v-if="!session" class="console-empty">
                <span>运行后，这里会按类别显示真实执行日志。</span>
            </div>
            <div v-else-if="!filteredEvents.length" class="console-empty">
                <span>{{ emptyMessage }}</span>
            </div>
            <button
                v-for="event in filteredEvents"
                :key="event.sequence"
                type="button"
                class="event-row"
                :data-level="event.level"
                :class="{ locatable: Boolean(event.instruction_id) }"
                :disabled="!event.instruction_id"
                :title="event.instruction_id ? '定位到产生这条日志的语句' : ''"
                @click="locateEvent(event)"
            >
                <time :datetime="event.timestamp">{{ shortTime(event.timestamp) }}</time>
                <span class="level-dot" :title="levelLabel(event.level)" aria-hidden="true"></span>
                <span class="event-category">{{ categoryLabel(event.category) }}</span>
                <span class="event-message">{{ event.message }}</span>
            </button>
        </div>

        <div v-else class="value-list" aria-label="当前变量与结果">
            <div v-if="!valueCount" class="console-empty">
                <span>{{ valuesEmptyMessage }}</span>
            </div>
            <template v-else>
                <section v-if="localValues.length" class="value-group">
                    <h3>当前函数</h3>
                    <div v-for="item in localValues" :key="`local:${item.id}`" class="value-row">
                        <span><strong>{{ item.display_name }}</strong><small>{{ typeLabel(item.value_type) }}</small></span>
                        <code :title="fullValue(item.value)">{{ displayValue(item.value) }}</code>
                    </div>
                </section>
                <section v-if="projectValues.length" class="value-group">
                    <h3>项目变量</h3>
                    <div v-for="item in projectValues" :key="`project:${item.id}`" class="value-row">
                        <span><strong>{{ item.display_name }}</strong><small>{{ typeLabel(item.value_type) }}</small></span>
                        <code :title="fullValue(item.value)">{{ displayValue(item.value) }}</code>
                    </div>
                </section>
            </template>
        </div>

        <footer v-if="session" class="console-footer">
            <span>{{ filteredEvents.length }} 条</span>
            <span v-if="session.error" class="run-error">{{ session.error }}</span>
            <span class="execution-id" :title="session.execution_id">{{ compactExecutionId }}</span>
        </footer>
    </section>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { ArrowDownToLine, Eraser, TerminalSquare, X } from 'lucide-vue-next'
import type { RuntimeEvent, RuntimeSession, RuntimeValueEntry } from '../types'
import { programTypeDisplayName } from './typePresentation'

const props = withDefaults(defineProps<{ session: RuntimeSession | null; embedded?: boolean; mode?: 'output' | 'values' }>(), { embedded: false, mode: 'output' })
const emit = defineEmits<{ close: []; locateStatement: [statementId: string] }>()

const activeCategory = ref('all')
const activeMode = ref<'log' | 'values'>('log')
const autoScroll = ref(true)
const hiddenThroughSequence = ref(0)
const eventList = ref<HTMLElement | null>(null)

const visibleEvents = computed(() => (props.session?.events || []).filter((event) => (
    event.sequence > hiddenThroughSequence.value
)))

const categoryNames: Record<string, string> = {
    script: '脚本',
    runtime: '运行',
    target: '目标',
    capture: '捕获',
    vision: '图像',
    ocr: '文字',
    input: '输入',
    extension: '扩展',
    network: '网络',
    message: '消息',
    filesystem: '文件',
    debug: '调试',
    worker: '运行器',
    popup: '弹窗处理',
}

const categories = computed(() => {
    const counts = new Map<string, number>()
    for (const event of visibleEvents.value) counts.set(event.category, (counts.get(event.category) || 0) + 1)
    return [
        { value: 'all', label: '全部', count: visibleEvents.value.length },
        ...[...counts.entries()]
            .sort(([left], [right]) => categoryLabel(left).localeCompare(categoryLabel(right), 'zh-CN'))
            .map(([value, count]) => ({ value, label: categoryLabel(value), count })),
    ]
})

const filteredEvents = computed(() => activeCategory.value === 'all'
    ? visibleEvents.value
    : visibleEvents.value.filter((event) => event.category === activeCategory.value))

const localValues = computed<RuntimeValueEntry[]>(() => props.session?.value_entries?.local || [])
const projectValues = computed<RuntimeValueEntry[]>(() => props.session?.value_entries?.project || [])
const valueCount = computed(() => localValues.value.length + projectValues.value.length)
const valuesEmptyMessage = computed(() => props.session?.status === 'paused'
    ? '当前暂停位置还没有可查看的值。'
    : '运行到产生变量或函数结果后，这里会显示当前值。')

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

const emptyMessage = computed(() => {
    if (visibleEvents.value.length && activeCategory.value !== 'all') return '当前分类还没有日志。'
    if (props.session?.status === 'running' || props.session?.status === 'queued') return '正在等待第一条运行日志…'
    return '本次运行没有可显示的日志。'
})

const compactExecutionId = computed(() => {
    const value = props.session?.execution_id || ''
    return value.length > 18 ? `${value.slice(0, 8)}…${value.slice(-6)}` : value
})

watch(() => props.session?.execution_id, () => {
    hiddenThroughSequence.value = 0
    activeCategory.value = 'all'
    activeMode.value = props.mode === 'values' ? 'values' : 'log'
})

watch(() => props.mode, value => { activeMode.value = value === 'values' ? 'values' : 'log' }, { immediate: true })

watch(() => filteredEvents.value.at(-1)?.sequence, async () => {
    if (!autoScroll.value) return
    await nextTick()
    const element = eventList.value
    if (!element) return
    if (typeof element.scrollTo === 'function') element.scrollTo({ top: element.scrollHeight })
    else element.scrollTop = element.scrollHeight
})

watch(categories, (items) => {
    if (!items.some((item) => item.value === activeCategory.value)) activeCategory.value = 'all'
})

function categoryLabel(category: string): string {
    return categoryNames[category] || category || '其他'
}

function levelLabel(level: RuntimeEvent['level']): string {
    if (level === 'error') return '错误'
    if (level === 'warning') return '警告'
    return '信息'
}

function shortTime(timestamp: string): string {
    const date = new Date(timestamp)
    if (Number.isNaN(date.getTime())) return timestamp
    return new Intl.DateTimeFormat('zh-CN', {
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    }).format(date)
}

function clearView(): void {
    hiddenThroughSequence.value = Math.max(0, ...visibleEvents.value.map((event) => event.sequence))
}

function locateEvent(event: RuntimeEvent): void {
    if (event.instruction_id) emit('locateStatement', event.instruction_id)
}

function typeLabel(valueType: string): string {
    return programTypeDisplayName(valueType)
}

function fullValue(value: unknown): string {
    if (value === null) return '空'
    if (value === undefined) return '未设置'
    if (typeof value === 'boolean') return value ? '开启' : '关闭'
    if (typeof value === 'string') return value
    try { return JSON.stringify(value, null, 2) }
    catch { return String(value) }
}

function displayValue(value: unknown): string {
    const result = fullValue(value).replace(/\s+/g, ' ').trim()
    return result.length > 180 ? `${result.slice(0, 177)}…` : result
}
</script>

<style scoped>
.run-console {
    min-height: 150px;
    height: min(270px, 36vh);
    display: grid;
    grid-template-rows: 38px auto minmax(0, 1fr) 24px;
    border-top: 1px solid var(--app-border-default);
    background: var(--app-bg-panel);
    color: var(--app-text-regular);
}
.run-console.embedded { width: 100%; height: 100%; min-height: 0; grid-template-rows: var(--app-control-default) auto minmax(0, 1fr) 24px; border-top: 0; }
.run-console.embedded.without-footer { grid-template-rows: var(--app-control-default) auto minmax(0, 1fr); }
.run-console.embedded.values-only { grid-template-rows: minmax(0, 1fr); }
.run-console.embedded.values-only .value-list { grid-row: 1; }

.console-header,
.console-footer,
.console-title,
.console-actions,
.category-tabs { display: flex; align-items: center; }

.console-header {
    grid-row: 1;
    justify-content: space-between;
    padding: 0 var(--app-spacing-sm) 0 var(--app-spacing-md);
    border-bottom: 1px solid var(--app-border-subtle);
}
.console-header.embedded { justify-content: flex-end; min-height: var(--app-control-default); padding-inline: var(--app-spacing-sm); }

.console-title { gap: var(--app-spacing-sm); }
.console-title > svg { color: var(--app-text-secondary); }
.console-title strong { color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; }

.status-pill {
    padding: 2px 7px;
    border-radius: 999px;
    background: var(--app-bg-hover);
    color: var(--app-text-secondary);
    font-size: var(--app-font-xs);
}
.status-pill[data-status="running"] { background: var(--app-color-primary-dim); color: var(--app-color-primary); }
.status-pill[data-status="completed"] { color: var(--app-color-success); }
.status-pill[data-status="failed"] { color: var(--app-color-danger); }
.status-pill[data-status="paused"] { color: var(--app-color-warning); }

.console-mode-tabs { display: flex; align-items: center; gap: 2px; margin-left: auto; margin-right: 8px; }
.console-mode-tabs button {
    height: 26px; padding: 0 9px; border: 0; border-radius: var(--app-radius-sm);
    background: transparent; color: var(--app-text-secondary); font: inherit; cursor: pointer;
}
.console-mode-tabs button:hover, .console-mode-tabs button.active { background: var(--app-bg-active); color: var(--app-text-primary); }
.console-mode-tabs span { margin-left: 4px; color: var(--app-text-placeholder); font-size: var(--app-font-xs); }

.console-actions { gap: 2px; }
.console-actions button {
    width: var(--app-control-compact);
    height: var(--app-control-compact);
    display: grid;
    place-items: center;
    padding: 0;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    cursor: pointer;
}
.console-actions button:hover:not(:disabled), .console-actions button:focus-visible { background: var(--app-bg-hover); color: var(--app-text-primary); }
.console-actions button.active { background: var(--app-color-primary-dim); color: var(--app-color-primary); }
.console-actions button:disabled { opacity: .35; cursor: default; }

.category-tabs {
    grid-row: 2;
    gap: 2px;
    min-height: var(--app-control-default);
    padding: 3px var(--app-spacing-md);
    overflow-x: auto;
    border-bottom: 1px solid var(--app-border-subtle);
}
.category-tabs button {
    height: 26px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    flex: 0 0 auto;
    padding: 0 9px;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    font: inherit;
    cursor: pointer;
}
.category-tabs button:hover, .category-tabs button:focus-visible { background: var(--app-bg-hover); color: var(--app-text-primary); }
.category-tabs button.active { background: var(--app-bg-active); color: var(--app-text-primary); }
.category-tabs span { color: var(--app-text-placeholder); font-size: var(--app-font-xs); }

.event-list { grid-row: 3; min-height: 0; overflow: auto; padding: 5px var(--app-spacing-sm); }
.event-row {
    width: 100%; border: 0; background: transparent; color: inherit; text-align: left; font-family: inherit;
    min-height: var(--app-control-compact);
    display: grid;
    grid-template-columns: 60px 8px 52px minmax(0, 1fr);
    align-items: start;
    gap: 8px;
    padding: 5px 8px;
    border-radius: var(--app-radius-sm);
    font-size: var(--app-font-xs);
    line-height: 18px;
}
.event-row.locatable:hover, .event-row.locatable:focus-visible { background: var(--app-bg-hover); outline: 0; box-shadow: var(--focus-ring); cursor: pointer; }
.event-row:disabled { opacity: 1; }
.event-row time { color: var(--app-text-placeholder); font-family: var(--app-font-mono); }
.level-dot { width: 6px; height: 6px; margin-top: 6px; border-radius: 50%; background: var(--app-text-placeholder); }
.event-row[data-level="warning"] .level-dot { background: var(--app-color-warning); }
.event-row[data-level="error"] .level-dot { background: var(--app-color-danger); }
.event-category { color: var(--app-text-secondary); }
.event-message { min-width: 0; color: var(--app-text-regular); overflow-wrap: anywhere; }
.event-row[data-level="error"] .event-message { color: color-mix(in srgb, var(--app-color-danger) 78%, var(--app-text-primary)); }

.console-empty { height: 100%; display: grid; place-items: center; padding: 20px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.console-footer { grid-row: 4; justify-content: space-between; gap: 12px; padding: 0 var(--app-spacing-md); border-top: 1px solid var(--app-border-subtle); color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.run-error { min-width: 0; flex: 1; overflow: hidden; color: var(--app-color-danger); text-overflow: ellipsis; white-space: nowrap; }
.execution-id { font-family: var(--app-font-mono); }

.value-list { grid-row: 3; min-height: 0; overflow: auto; padding: 6px var(--app-spacing-md) 10px; }
.value-group + .value-group { margin-top: 10px; }
.value-group h3 { margin: 5px 7px; color: var(--app-text-secondary); font-size: var(--app-font-xs); font-weight: 600; }
.value-row { min-height: var(--app-control-default); display: grid; grid-template-columns: minmax(120px, .8fr) minmax(0, 1.6fr); align-items: center; gap: 12px; padding: 5px 8px; border-bottom: 1px solid var(--app-border-subtle); }
.value-row > span { min-width: 0; display: flex; align-items: baseline; gap: 7px; }
.value-row strong { overflow: hidden; color: var(--app-text-primary); font-size: var(--app-font-xs); font-weight: 550; text-overflow: ellipsis; white-space: nowrap; }
.value-row small { flex: none; color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.value-row code { min-width: 0; overflow: hidden; color: var(--app-text-regular); font-family: var(--app-font-mono); font-size: var(--app-font-xs); text-overflow: ellipsis; white-space: nowrap; }

@media (max-height: 700px) { .run-console { height: min(210px, 32vh); } }
</style>
