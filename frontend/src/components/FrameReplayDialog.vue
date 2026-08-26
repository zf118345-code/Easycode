<template>
    <el-dialog
        v-model="visible"
        title="历史帧工作台"
        width="min(1180px, 94vw)"
        class="frame-replay-dialog"
        :close-on-click-modal="false"
        @opened="loadSessions"
        @closed="closeWorkbench">
        <div class="replay-layout" tabindex="0" @keydown.left.prevent="stepFrame(-1)" @keydown.right.prevent="stepFrame(1)">
            <aside class="session-panel">
                <div class="panel-heading">
                    <History :size="15" />
                    <span>录制会话</span>
                    <el-button text circle :loading="loadingSessions" @click="loadSessions"><RefreshCw :size="14" /></el-button>
                </div>
                <el-scrollbar class="session-list">
                    <button
                        v-for="session in sessions"
                        :key="session.session_id"
                        type="button"
                        class="session-item"
                        :class="{ active: session.session_id === activeSessionId }"
                        @click="selectSession(session)">
                        <span class="session-title">{{ session.target_title || '未命名目标' }}</span>
                        <span class="session-meta">{{ formatTime(session.started_at) }}</span>
                        <span class="session-meta">{{ session.frame_count }} 帧 · {{ formatBytes(session.total_bytes) }}</span>
                    </button>
                    <el-empty v-if="!loadingSessions && !sessions.length" description="还没有逐帧录制" :image-size="72" />
                </el-scrollbar>
            </aside>

            <main class="frame-stage">
                <div class="stage-toolbar">
                    <div>
                        <strong>{{ activeSession?.target_title || '选择录制会话' }}</strong>
                        <span v-if="currentFrame" class="frame-caption">第 {{ currentIndex }} / {{ frameTotal }} 帧</span>
                    </div>
                    <div class="toolbar-actions">
                        <el-button :disabled="!currentFrame" @click="togglePlayback">
                            <Pause v-if="playing" :size="14" /><Play v-else :size="14" /> {{ playing ? '暂停' : '播放' }}
                        </el-button>
                        <el-select v-model="playbackFps" class="fps-select" size="small" title="回放速度">
                            <el-option v-for="fps in [2, 5, 10, 20]" :key="fps" :label="`${fps} FPS`" :value="fps" />
                        </el-select>
                        <el-switch v-model="collapseSimilar" inline-prompt active-text="去重" inactive-text="全帧" title="折叠变化很小的相似帧" />
                        <el-button :disabled="!currentFrame" title="跳到下一张明显变化帧" @click="stepChanged"><SkipForward :size="14" /></el-button>
                        <el-button :disabled="!currentFrame || analyzing" @click="analyzeCurrent">
                            <ScanSearch :size="14" /> 离线识别
                        </el-button>
                        <el-button :disabled="!activeSessionId || regressing" :loading="regressing" @click="analyzeWholeSession">
                            <ListChecks :size="14" /> 整段回归
                        </el-button>
                        <el-button v-if="regression" title="导出逐帧命中与耗时报告" @click="exportRegression">
                            <Download :size="14" /> 报告
                        </el-button>
                        <el-button type="primary" :disabled="!currentFrame || openingCapture" :loading="openingCapture" @click="captureCurrent">
                            <Focus :size="14" /> 从此帧捕获节点
                        </el-button>
                    </div>
                </div>

                <div class="image-stage" v-loading="loadingFrame">
                    <img v-if="frameUrl" :src="frameUrl" alt="历史录制帧" />
                    <el-empty v-else description="请选择一帧" :image-size="84" />
                </div>

                <div v-if="frameTotal" class="thumbnail-timeline">
                    <button v-for="frame in thumbnailFrames" :key="frame.index" type="button" :class="{ active: frame.index === currentIndex }" @click="selectFrameIndex(frame.index)">
                        <img v-if="thumbnailUrls.get(frame.index)" :src="thumbnailUrls.get(frame.index)" alt="录制帧缩略图">
                        <span>{{ frame.index }}</span>
                    </button>
                </div>
                <div v-if="frameTotal" class="timeline-panel">
                    <el-button text circle :disabled="currentIndex <= 1" @click="stepFrame(-1)"><ChevronLeft :size="17" /></el-button>
                    <el-slider
                        v-model="currentIndex"
                        :min="1"
                        :max="frameTotal"
                        :show-tooltip="true"
                        @change="selectFrameIndex" />
                    <el-button text circle :disabled="currentIndex >= frameTotal" @click="stepFrame(1)"><ChevronRight :size="17" /></el-button>
                </div>
                <div v-if="currentFrame" class="frame-info">
                    <span>{{ formatTime(currentFrame.captured_at) }}</span>
                    <span>{{ currentFrame.width }} × {{ currentFrame.height }}</span>
                    <span>{{ formatBytes(currentFrame.bytes) }}</span>
                    <span>← → 逐帧</span>
                </div>
            </main>

            <aside class="analysis-panel">
                <div class="panel-heading"><Activity :size="15" /><span>离线识别结果</span></div>
                <el-scrollbar class="analysis-scroll" v-loading="analyzing || regressing">
                    <template v-if="analysis">
                        <div class="analysis-summary">
                            耗时 {{ analysis.elapsed_ms }} ms · 命中 {{ analysis.matched_pages?.length || 0 }} 个页面
                        </div>
                        <div
                            v-for="page in analysis.pages"
                            :key="page.node_id"
                            class="page-result"
                            :class="{ matched: page.matched }">
                            <div class="page-result-title">
                                <CheckCircle2 v-if="page.matched" :size="14" />
                                <CircleX v-else :size="14" />
                                <span>{{ page.node_name }}</span>
                            </div>
                            <div class="page-result-meta">
                                {{ page.elapsed_ms }} ms
                                <span v-if="page.last_match_score"> · {{ page.last_match_score.toFixed(2) }}</span>
                            </div>
                            <div v-if="page.last_ocr_text" class="ocr-text">OCR：{{ page.last_ocr_text }}</div>
                        </div>
                    </template>
                    <template v-else-if="regression">
                        <div class="analysis-summary">
                            已回归 {{ regression.analyzed_frame_count }} / {{ regression.source_frame_count }} 帧<br>
                            总耗时 {{ regression.elapsed_ms }} ms · P95 {{ regression.frame_analysis_p95_ms }} ms<br>
                            无页面命中 {{ regression.unmatched_frame_count }} 帧 · 校验/读取错误 {{ regression.error_frame_count || 0 }} 帧
                        </div>
                        <div v-if="regression.error_frame_count" class="regression-errors">
                            <div v-for="frame in regression.frames.filter(item => item.error).slice(0, 12)" :key="frame.frame_index">
                                第 {{ frame.frame_index }} 帧：{{ frame.error }}
                            </div>
                        </div>
                        <div v-for="page in regression.coverage" :key="page.node_id" class="page-result" :class="{ matched: page.matched_frames }">
                            <div class="page-result-title"><ListChecks :size="14" /><span>{{ page.node_name }}</span></div>
                            <div class="page-result-meta">命中 {{ page.matched_frames }} 帧 · 首次第 {{ page.first_frame || '-' }} 帧</div>
                        </div>
                    </template>
                    <el-empty v-else description="点击“离线识别”验证当前拓扑" :image-size="68" />
                </el-scrollbar>
            </aside>
        </div>
        <template #footer>
            <span class="footer-tip">历史帧捕获复用现有捕获链，生成节点后仍按当前画布选择和连线语义处理。</span>
            <el-button @click="visible = false">关闭</el-button>
        </template>
    </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
    Activity, CheckCircle2, ChevronLeft, ChevronRight, CircleX,
    Download, Focus, History, ListChecks, Pause, Play, RefreshCw, ScanSearch, SkipForward
} from 'lucide-vue-next'
import { frameRecordingApi } from '@/api/frameRecordingApi'
import { captureApi } from '@/api/captureApi'
import { useProjectStore } from '@/stores/projectStore'
import { downloadBlob } from '@/utils/download'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue'])
const projectStore = useProjectStore()

const visible = computed({ get: () => props.modelValue, set: value => emit('update:modelValue', value) })
const sessions = ref([])
const activeSessionId = ref('')
const frameTotal = ref(0)
const frameMap = ref(new Map())
const currentIndex = ref(1)
const frameUrl = ref('')
const thumbnailUrls = ref(new Map())
const analysis = ref(null)
const loadingSessions = ref(false)
const loadingFrame = ref(false)
const analyzing = ref(false)
const regressing = ref(false)
const openingCapture = ref(false)
const playing = ref(false)
const playbackFps = ref(10)
const collapseSimilar = ref(false)
const regression = ref(null)
let imageRequestId = 0
let playbackTimer = null

const activeSession = computed(() => sessions.value.find(item => item.session_id === activeSessionId.value) || null)
const currentFrame = computed(() => frameMap.value.get(Number(currentIndex.value)) || null)
const thumbnailFrames = computed(() => {
    const start = Math.max(1, currentIndex.value - 3)
    const end = Math.min(frameTotal.value, currentIndex.value + 3)
    const result = []
    for (let index = start; index <= end; index += 1) result.push(frameMap.value.get(index) || { index })
    return result
})

const releaseImage = () => {
    imageRequestId += 1
    if (frameUrl.value) URL.revokeObjectURL(frameUrl.value)
    frameUrl.value = ''
    for (const url of thumbnailUrls.value.values()) URL.revokeObjectURL(url)
    thumbnailUrls.value = new Map()
}
const pausePlayback = () => {
    playing.value = false
    if (playbackTimer) clearTimeout(playbackTimer)
    playbackTimer = null
}
const closeWorkbench = () => {
    pausePlayback()
    releaseImage()
}

const formatBytes = value => {
    const bytes = Number(value || 0)
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
const formatTime = value => {
    if (!value) return '时间未知'
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

const loadSessions = async () => {
    if (!projectStore.currentProjectPath) return
    loadingSessions.value = true
    try {
        const result = await frameRecordingApi.listSessions(projectStore.currentProjectPath)
        sessions.value = result.sessions || []
        if (sessions.value.length && !sessions.value.some(item => item.session_id === activeSessionId.value)) {
            await selectSession(sessions.value[0])
        }
    } catch (error) {
        ElMessage.error(error?.message || '读取录制会话失败')
    } finally {
        loadingSessions.value = false
    }
}

const ensureFramePage = async index => {
    const wanted = Math.max(1, Math.min(Number(index || 1), frameTotal.value || 1))
    if (frameMap.value.has(wanted)) return
    const offset = Math.floor((wanted - 1) / 200) * 200
    const result = await frameRecordingApi.listFrames(projectStore.currentProjectPath, activeSessionId.value, offset, 200)
    frameTotal.value = Number(result.total || 0)
    const next = new Map(frameMap.value)
    for (const frame of result.frames || []) next.set(Number(frame.index), frame)
    frameMap.value = next
}

const loadThumbnailsAround = async index => {
    const sessionId = activeSessionId.value
    const start = Math.max(1, Number(index) - 3)
    const end = Math.min(frameTotal.value, Number(index) + 3)
    await Promise.all(Array.from({ length: end - start + 1 }, (_, offset) => start + offset).map(async frameIndex => {
        if (thumbnailUrls.value.has(frameIndex)) return
        try {
            const blob = await frameRecordingApi.getFrameThumbnail(projectStore.currentProjectPath, sessionId, frameIndex)
            if (sessionId !== activeSessionId.value) return
            const next = new Map(thumbnailUrls.value)
            if (!next.has(frameIndex)) {
                next.set(frameIndex, URL.createObjectURL(blob))
            }
            thumbnailUrls.value = next
        } catch { /* 单个缩略图失败不阻断原图回看 */ }
    }))
}

const selectSession = async session => {
    imageRequestId += 1
    activeSessionId.value = session.session_id
    frameMap.value = new Map()
    releaseImage()
    frameTotal.value = Number(session.frame_count || 0)
    currentIndex.value = 1
    analysis.value = null
    regression.value = null
    pausePlayback()
    if (frameTotal.value) await selectFrameIndex(1)
    else releaseImage()
}

const selectFrameIndex = async value => {
    if (!activeSessionId.value || !frameTotal.value) return
    const index = Math.max(1, Math.min(Number(value || 1), frameTotal.value))
    currentIndex.value = index
    analysis.value = null
    loadingFrame.value = true
    const requestId = ++imageRequestId
    try {
        await ensureFramePage(index)
        loadThumbnailsAround(index)
        const blob = await frameRecordingApi.getFrameImage(projectStore.currentProjectPath, activeSessionId.value, index)
        if (requestId !== imageRequestId) return
        if (frameUrl.value) URL.revokeObjectURL(frameUrl.value)
        frameUrl.value = URL.createObjectURL(blob)
    } catch (error) {
        if (requestId === imageRequestId) ElMessage.error(error?.message || '读取录制帧失败')
    } finally {
        if (requestId === imageRequestId) loadingFrame.value = false
    }
}

const findChangedIndex = async (start, direction) => {
    for (let index = start; index >= 1 && index <= frameTotal.value; index += direction) {
        await ensureFramePage(index)
        if (Number(frameMap.value.get(index)?.change_score || 0) >= 0.006 || index === 1) return index
    }
    return null
}

const stepFrame = async delta => {
    if (!frameTotal.value) return false
    let target = Math.max(1, Math.min(frameTotal.value, currentIndex.value + delta))
    if (collapseSimilar.value && delta) {
        target = await findChangedIndex(target, delta > 0 ? 1 : -1)
        if (target == null) return false
    }
    await selectFrameIndex(target)
    return true
}

const playbackLoop = async () => {
    if (!playing.value) return
    if (currentIndex.value >= frameTotal.value) {
        pausePlayback()
        return
    }
    const advanced = await stepFrame(1)
    if (!advanced) return pausePlayback()
    if (playing.value) playbackTimer = setTimeout(playbackLoop, Math.max(20, 1000 / playbackFps.value))
}
const togglePlayback = () => {
    if (playing.value) return pausePlayback()
    if (currentIndex.value >= frameTotal.value) currentIndex.value = 1
    playing.value = true
    playbackLoop()
}

const stepChanged = async () => {
    pausePlayback()
    const target = await findChangedIndex(currentIndex.value + 1, 1)
    if (target != null) return selectFrameIndex(target)
    ElMessage.info('后面没有明显变化帧')
}

const analyzeCurrent = async () => {
    if (!currentFrame.value) return
    analyzing.value = true
    regression.value = null
    try {
        analysis.value = await frameRecordingApi.analyzeFrame(
            projectStore.currentProjectPath, activeSessionId.value, currentIndex.value
        )
    } catch (error) {
        ElMessage.error(error?.message || '离线识别失败')
    } finally {
        analyzing.value = false
    }
}

const analyzeWholeSession = async () => {
    if (!activeSessionId.value) return
    regressing.value = true
    analysis.value = null
    try {
        regression.value = await frameRecordingApi.analyzeSession(
            projectStore.currentProjectPath,
            activeSessionId.value,
            { changes_only: false, step: 1, max_frames: 10000 }
        )
    } catch (error) {
        ElMessage.error(error?.message || '整段视觉回归失败')
    } finally {
        regressing.value = false
    }
}

const exportRegression = () => {
    if (!regression.value) return
    const safeSession = activeSessionId.value || 'recording'
    downloadBlob(
        new Blob([JSON.stringify(regression.value, null, 2)], { type: 'application/json;charset=utf-8' }),
        `${safeSession}-visual-regression.json`
    )
}

const captureCurrent = async () => {
    if (!currentFrame.value) return
    openingCapture.value = true
    try {
        await captureApi.replay(activeSessionId.value, currentIndex.value)
        visible.value = false
    } catch (error) {
        ElMessage.error(error?.message || '历史帧捕获启动失败')
    } finally {
        openingCapture.value = false
    }
}
</script>

<style scoped>
.replay-layout { height: min(690px, 72vh); display: grid; grid-template-columns: 220px minmax(0, 1fr) 260px; border: 1px solid var(--el-border-color); border-radius: 8px; overflow: hidden; outline: none; }
.session-panel, .analysis-panel { min-width: 0; background: var(--el-bg-color-page); }
.session-panel { border-right: 1px solid var(--el-border-color); }
.analysis-panel { border-left: 1px solid var(--el-border-color); }
.panel-heading { height: 42px; padding: 0 12px; display: flex; align-items: center; gap: 7px; border-bottom: 1px solid var(--el-border-color); font-weight: 600; }
.panel-heading .el-button { margin-left: auto; }
.session-list, .analysis-scroll { height: calc(100% - 43px); }
.session-item { width: 100%; border: 0; border-bottom: 1px solid var(--el-border-color-lighter); padding: 10px 12px; background: transparent; color: inherit; display: flex; flex-direction: column; align-items: flex-start; gap: 4px; cursor: pointer; text-align: left; }
.session-item:hover { background: var(--el-fill-color-light); }
.session-item.active { background: var(--el-color-primary-light-9); box-shadow: inset 3px 0 var(--el-color-primary); }
.session-title { width: 100%; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.session-meta, .frame-caption, .frame-info, .page-result-meta { color: var(--el-text-color-secondary); font-size: 11px; }
.frame-stage { min-width: 0; display: grid; grid-template-rows: 48px minmax(0, 1fr) auto auto auto; background: #0f1012; }
.stage-toolbar { padding: 0 12px; display: flex; align-items: center; justify-content: space-between; background: var(--el-bg-color); border-bottom: 1px solid var(--el-border-color); }
.stage-toolbar > div:first-child { display: flex; flex-direction: column; gap: 2px; }
.toolbar-actions { display: flex; gap: 8px; }
.toolbar-actions .el-button { display: inline-flex; gap: 5px; }
.fps-select { width: 82px; }
.image-stage { min-height: 0; display: flex; align-items: center; justify-content: center; overflow: auto; background: repeating-conic-gradient(#15171a 0 25%, #111315 0 50%) 0/18px 18px; }
.image-stage img { max-width: 100%; max-height: 100%; object-fit: contain; image-rendering: auto; }
.timeline-panel { padding: 8px 12px 2px; display: grid; grid-template-columns: 28px minmax(0, 1fr) 28px; gap: 8px; align-items: center; background: var(--el-bg-color); }
.thumbnail-timeline { display:flex; justify-content:center; gap:5px; padding:7px 12px 0; background:var(--el-bg-color); min-height:58px; }
.thumbnail-timeline button { position:relative; width:72px; height:48px; padding:0; overflow:hidden; border:1px solid var(--el-border-color); border-radius:4px; background:var(--el-fill-color); color:var(--el-text-color-secondary); cursor:pointer; }
.thumbnail-timeline button.active { border-color:var(--el-color-primary); box-shadow:0 0 0 1px var(--el-color-primary); }
.thumbnail-timeline img { width:100%; height:100%; object-fit:cover; }
.thumbnail-timeline span { position:absolute; right:2px; bottom:1px; padding:0 3px; border-radius:3px; background:rgba(0,0,0,.7); color:#fff; font-size:10px; }
.frame-info { min-height: 25px; padding: 0 16px 7px; display: flex; gap: 14px; justify-content: center; background: var(--el-bg-color); }
.analysis-summary { margin: 10px; padding: 9px; border-radius: 6px; background: var(--el-fill-color-light); font-size: 12px; }
.regression-errors { margin: 0 10px 10px; padding: 8px; border: 1px solid var(--el-color-danger-light-5); border-radius: 6px; color: var(--el-color-danger); font-size: 11px; line-height: 1.55; }
.page-result { margin: 0 10px 8px; padding: 9px; border: 1px solid var(--el-border-color); border-radius: 7px; }
.page-result.matched { border-color: var(--el-color-success); background: var(--el-color-success-light-9); }
.page-result-title { display: flex; align-items: center; gap: 6px; font-weight: 600; }
.page-result.matched .page-result-title { color: var(--el-color-success); }
.page-result-meta, .ocr-text { margin-top: 5px; }
.ocr-text { font-size: 11px; word-break: break-all; }
.footer-tip { margin-right: auto; color: var(--el-text-color-secondary); font-size: 12px; }
:deep(.el-dialog__footer) { display: flex; align-items: center; }
@media (max-width: 900px) { .replay-layout { grid-template-columns: 180px minmax(0, 1fr); } .analysis-panel { display: none; } }
</style>
