<!-- 唯一 IDE 运行日志入口：分类仅改变视图，原始日志始终完整保留。 -->
<template>
    <section class="canvas-log-panel" aria-label="运行日志">
        <div class="log-command-bar">
            <div class="log-filters" role="toolbar" aria-label="日志分类">
                <button
                    v-for="filter in filterOptions"
                    :key="filter.key"
                    type="button"
                    class="log-filter-button"
                    :class="{ 'is-active': activeFilter === filter.key }"
                    :aria-pressed="activeFilter === filter.key"
                    @click="selectFilter(filter.key)">
                    <span>{{ filter.label }}</span>
                    <span class="filter-count">{{ filterCounts[filter.key] }}</span>
                </button>
            </div>

            <div class="log-actions" role="toolbar" aria-label="日志操作">
                <el-tooltip content="复制全部日志" placement="top">
                    <button
                        type="button"
                        class="log-action-button"
                        :disabled="!normalizedLogs.length"
                        aria-label="复制全部日志"
                        @click="copyLogs">
                        <Copy />
                    </button>
                </el-tooltip>
                <el-tooltip content="清空全部日志" placement="top">
                    <button
                        type="button"
                        class="log-action-button is-danger"
                        :disabled="!normalizedLogs.length"
                        aria-label="清空全部日志"
                        @click="clearLogs">
                        <Trash2 />
                    </button>
                </el-tooltip>
            </div>
        </div>

        <div
            ref="logBodyRef"
            class="log-panel-body"
            role="log"
            aria-live="off"
            @scroll="onScroll">
            <div v-if="!normalizedLogs.length" class="log-empty-state">
                <TerminalSquare />
                <span>运行后将在这里显示日志</span>
            </div>
            <div v-else-if="!filteredLogs.length" class="log-empty-state">
                <ListFilter />
                <span>当前分类暂无日志</span>
                <button type="button" @click="selectFilter('all')">显示全部</button>
            </div>
            <div v-else class="log-virtual-spacer" :style="{ height: `${totalHeight}px` }">
                <div
                    v-for="entry in visibleLogs"
                    :key="entry.log.key"
                    class="log-line"
                    :class="`is-${entry.log.level}`"
                    :style="{ transform: `translateY(${entry.index * ROW_HEIGHT}px)` }">
                    <span class="log-time">{{ entry.log.time }}</span>
                    <span class="log-category">{{ categoryLabels[entry.log.category] }}</span>
                    <span class="log-severity" :aria-label="levelLabels[entry.log.level]">
                        <CircleAlert v-if="entry.log.level === 'error'" />
                        <TriangleAlert v-else-if="entry.log.level === 'warning'" />
                        <span v-else class="info-mark" aria-hidden="true" />
                    </span>
                    <span class="log-text">{{ entry.log.text }}</span>
                </div>
            </div>
        </div>
        <button
            v-if="!isFollowing && filteredLogs.length"
            type="button"
            class="jump-latest-button"
            @click="jumpToLatest">
            <ArrowDownToLine />
            <span>回到最新</span>
            <span v-if="pendingCount" class="pending-count">{{ pendingCount }}</span>
        </button>
    </section>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
    ArrowDownToLine,
    CircleAlert,
    Copy,
    ListFilter,
    TerminalSquare,
    Trash2,
    TriangleAlert
} from 'lucide-vue-next'
import { useExecutionStore } from '@/stores'
import {
    isLogInFilter,
    LOG_CATEGORY_OPTIONS,
    normalizeLogItem
} from '@/utils/logModel'

const execStore = useExecutionStore()
const logBodyRef = ref(null)
const activeFilter = ref('all')
const isFollowing = ref(true)
const pendingCount = ref(0)
const scrollTop = ref(0)
const viewportHeight = ref(300)
let resizeObserver = null

const ROW_HEIGHT = 22
const OVERSCAN = 10
const categoryLabels = Object.freeze(Object.fromEntries(LOG_CATEGORY_OPTIONS.map(item => [item.key, item.label])))
const levelLabels = Object.freeze({ info: '信息', warning: '警告', error: '错误' })
const filterOptions = LOG_CATEGORY_OPTIONS

const normalizedLogs = computed(() => (execStore.executionLogs || []).map(normalizeLogItem))
const filteredLogs = computed(() => normalizedLogs.value.filter(log => isLogInFilter(log, activeFilter.value)))
const filterCounts = computed(() => {
    const counts = Object.fromEntries(LOG_CATEGORY_OPTIONS.map(item => [item.key, 0]))
    for (const log of normalizedLogs.value) {
        counts.all += 1
        counts[log.category] += 1
        if (['warning', 'error'].includes(log.level)) counts.issues += 1
    }
    return counts
})
const totalHeight = computed(() => filteredLogs.value.length * ROW_HEIGHT)
const startIndex = computed(() => Math.max(0, Math.floor(scrollTop.value / ROW_HEIGHT) - OVERSCAN))
const endIndex = computed(() => Math.min(
    filteredLogs.value.length,
    Math.ceil((scrollTop.value + viewportHeight.value) / ROW_HEIGHT) + OVERSCAN
))
const visibleLogs = computed(() => filteredLogs.value
    .slice(startIndex.value, endIndex.value)
    .map((log, offset) => ({ log, index: startIndex.value + offset })))

const isNearBottom = element => element.scrollHeight - element.scrollTop - element.clientHeight <= ROW_HEIGHT * 2

function onScroll() {
    const element = logBodyRef.value
    if (!element) return
    scrollTop.value = element.scrollTop
    isFollowing.value = isNearBottom(element)
    if (isFollowing.value) pendingCount.value = 0
}

function jumpToLatest() {
    isFollowing.value = true
    pendingCount.value = 0
    nextTick(() => {
        const element = logBodyRef.value
        if (!element) return
        element.scrollTop = element.scrollHeight
        scrollTop.value = element.scrollTop
    })
}

function selectFilter(filter) {
    if (activeFilter.value === filter) return
    activeFilter.value = filter
    jumpToLatest()
}

function clearLogs() {
    execStore.clearLogs()
    activeFilter.value = 'all'
    isFollowing.value = true
    pendingCount.value = 0
}

async function copyLogs() {
    const text = normalizedLogs.value.map(log => `[${log.time}] ${log.text}`).join('\n')
    if (!text) return
    try {
        if (navigator.clipboard?.writeText) {
            await navigator.clipboard.writeText(text)
        } else {
            const textarea = document.createElement('textarea')
            textarea.value = text
            textarea.setAttribute('readonly', '')
            textarea.style.position = 'fixed'
            textarea.style.opacity = '0'
            document.body.appendChild(textarea)
            textarea.select()
            const copied = document.execCommand('copy')
            textarea.remove()
            if (!copied) throw new Error('浏览器拒绝复制命令')
        }
        ElMessage.success(`已复制 ${normalizedLogs.value.length} 条日志`)
    } catch (error) {
        ElMessage.error(`复制日志失败：${error?.message || '剪贴板不可用'}`)
    }
}

watch(() => [filteredLogs.value.length, filteredLogs.value.at(-1)?.key || ''], ([length, token], [previousLength, previousToken]) => {
    if (token === previousToken && length === previousLength) return
    if (length < previousLength) {
        pendingCount.value = 0
        return jumpToLatest()
    }
    const added = Math.max(1, length - previousLength)
    if (!added) return
    if (isFollowing.value) jumpToLatest()
    else pendingCount.value += added
})

onMounted(() => {
    const element = logBodyRef.value
    if (!element) return
    viewportHeight.value = element.clientHeight || 300
    resizeObserver = new ResizeObserver(() => {
        if (logBodyRef.value) viewportHeight.value = logBodyRef.value.clientHeight || 300
    })
    resizeObserver.observe(element)
    jumpToLatest()
})
onUnmounted(() => resizeObserver?.disconnect())
</script>

<style scoped>
.canvas-log-panel {
    position: relative;
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    color: var(--app-text-regular);
    background: var(--app-bg-panel);
}

.log-command-bar {
    min-height: 36px;
    padding: 4px 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 1px solid var(--app-separator);
    background: var(--app-sidebar-bg);
}

.log-filters {
    min-width: 0;
    display: flex;
    align-items: center;
    gap: 2px;
    overflow-x: auto;
    scrollbar-width: none;
}

.log-filters::-webkit-scrollbar {
    display: none;
}

.log-filter-button,
.log-action-button,
.jump-latest-button,
.log-empty-state button {
    border: 0;
    font: inherit;
    cursor: pointer;
}

.log-filter-button {
    height: 27px;
    padding: 0 8px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    flex: 0 0 auto;
    border-radius: var(--app-radius-sm);
    color: var(--app-text-secondary);
    background: transparent;
    font-size: 11px;
}

.log-filter-button:hover {
    color: var(--app-text-primary);
    background: var(--app-bg-hover);
}

.log-filter-button.is-active {
    color: var(--app-text-primary);
    background: var(--app-color-primary-dim);
    box-shadow: inset 0 -2px var(--app-color-primary);
}

.log-filter-button:focus-visible,
.log-action-button:focus-visible,
.jump-latest-button:focus-visible,
.log-empty-state button:focus-visible {
    outline: 0;
    box-shadow: var(--focus-ring);
}

.filter-count,
.pending-count {
    min-width: 16px;
    padding: 0 4px;
    border-radius: 999px;
    color: var(--app-text-placeholder);
    background: var(--app-bg-input);
    font-size: 10px;
    font-variant-numeric: tabular-nums;
    text-align: center;
}

.log-filter-button.is-active .filter-count {
    color: var(--app-text-regular);
}

.log-actions {
    margin-left: auto;
    padding-left: 8px;
    display: flex;
    align-items: center;
    gap: 2px;
    border-left: 1px solid var(--app-separator);
}

.log-action-button {
    width: 28px;
    height: 28px;
    display: grid;
    place-items: center;
    border-radius: var(--app-radius-sm);
    color: var(--app-text-secondary);
    background: transparent;
}

.log-action-button svg {
    width: 14px;
    height: 14px;
}

.log-action-button:hover:not(:disabled) {
    color: var(--app-text-primary);
    background: var(--app-bg-hover);
}

.log-action-button.is-danger:hover:not(:disabled) {
    color: var(--app-color-danger);
    background: var(--app-color-danger-soft);
}

.log-action-button:disabled {
    color: var(--app-text-disabled);
    cursor: default;
}

.log-panel-body {
    position: relative;
    flex: 1;
    min-height: 0;
    padding: 5px 8px 10px;
    overflow: auto;
    overscroll-behavior: contain;
    font-family: var(--app-font-mono);
    font-size: 11px;
    user-select: text;
}

.log-virtual-spacer {
    position: relative;
    width: 100%;
}

.log-line {
    position: absolute;
    inset: 0 0 auto;
    height: 22px;
    padding: 0 6px;
    display: grid;
    grid-template-columns: 58px 34px 14px minmax(0, 1fr);
    align-items: center;
    gap: 7px;
    border-radius: 4px;
    color: var(--app-text-regular);
    line-height: 18px;
}

.log-line:hover {
    background: var(--app-bg-hover);
}

.log-time {
    color: var(--app-text-placeholder);
    font-variant-numeric: tabular-nums;
}

.log-category {
    color: var(--app-text-secondary);
    font-family: var(--app-font-sans);
    font-size: 10px;
}

.log-severity {
    width: 14px;
    height: 14px;
    display: grid;
    place-items: center;
    color: var(--app-text-placeholder);
}

.log-severity svg {
    width: 13px;
    height: 13px;
}

.info-mark {
    width: 3px;
    height: 3px;
    border-radius: 50%;
    background: currentColor;
}

.log-text {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: pre;
}

.log-line.is-warning .log-severity,
.log-line.is-warning .log-text {
    color: var(--app-color-warning);
}

.log-line.is-error .log-severity,
.log-line.is-error .log-text {
    color: var(--app-color-danger);
}

.log-empty-state {
    min-height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    color: var(--app-text-placeholder);
    font-family: var(--app-font-sans);
    font-size: 11px;
}

.log-empty-state > svg {
    width: 15px;
    height: 15px;
}

.log-empty-state button {
    padding: 3px 5px;
    border-radius: var(--app-radius-sm);
    color: var(--app-color-primary);
    background: transparent;
}

.log-empty-state button:hover {
    background: var(--app-color-primary-dim);
}

.jump-latest-button {
    position: absolute;
    left: 50%;
    bottom: 8px;
    z-index: 2;
    height: 28px;
    padding: 0 9px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transform: translateX(-50%);
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-md);
    color: var(--app-text-primary);
    background: var(--app-bg-raised);
    box-shadow: var(--app-shadow-md);
    font-family: var(--app-font-sans);
    font-size: 11px;
}

.jump-latest-button:hover {
    border-color: var(--app-border-strong);
    background: var(--app-bg-hover);
}

.jump-latest-button svg {
    width: 13px;
    height: 13px;
}

@media (max-width: 760px) {
    .log-command-bar {
        gap: 4px;
    }

    .log-filter-button {
        padding-inline: 6px;
    }

    .log-line {
        grid-template-columns: 52px 14px minmax(0, 1fr);
    }

    .log-category {
        display: none;
    }
}
</style>
