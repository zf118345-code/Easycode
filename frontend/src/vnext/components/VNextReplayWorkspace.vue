<template>
    <div :class="['replay-workspace', { 'detail-panel-collapsed': !detailVisible }]" data-testid="replay-workspace">
        <div v-if="sessionsOpen || detailOverlayOpen" class="replay-scrim" aria-hidden="true" @click="closeOverlays"></div>
        <VNextIconButton
            ref="sessionsToggle"
            class="quiet-icon sessions-toggle"
            label="打开录制会话"
            @click="sessionsOpen = true"
        >
            <PanelLeft aria-hidden="true" />
        </VNextIconButton>
        <aside
            ref="sessionsElement"
            :class="['replay-sessions', { 'is-open': sessionsOpen }]"
            aria-label="录制会话"
            :role="sessionsOpen ? 'dialog' : undefined"
            :aria-modal="sessionsOpen ? 'true' : undefined"
            :tabindex="sessionsOpen ? -1 : undefined"
            @keydown="trapDialogFocus"
            @keydown.esc.stop="sessionsOpen = false"
        >
            <VNextPaneHeader class="pane-header" title="运行记录" :meta="`${filteredSessions.length} 个会话`" icon-only-actions>
                <template #actions><div class="pane-header-actions">
                    <VNextIconButton class="quiet-icon" label="刷新会话" :disabled="rootBusy" @click="refreshAll"><RefreshCw aria-hidden="true" /></VNextIconButton>
                    <VNextIconButton class="quiet-icon sessions-close" data-dialog-initial-focus label="关闭录制会话" @click="sessionsOpen = false"><X /></VNextIconButton>
                </div></template>
            </VNextPaneHeader>

            <section class="recording-strip" aria-label="逐帧录制">
                <div class="recording-heading">
                    <span :class="['status-dot', { active: recording.active }]" aria-hidden="true"></span>
                    <div><strong>{{ recording.active ? '正在录制' : '逐帧录制' }}</strong><small>{{ recordingSummary }}</small></div>
                </div>
                <template v-if="recording.active">
                    <dl class="live-stats">
                        <div><dt>已保存</dt><dd>{{ recording.frame_count }} 帧</dd></div>
                        <div><dt>占用</dt><dd>{{ formatBytes(recording.disk_bytes) }}</dd></div>
                        <div><dt>未保存</dt><dd>{{ recording.dropped_frame_count }} 帧</dd></div>
                    </dl>
                    <div class="recording-actions">
                        <input v-model="markerLabel" maxlength="120" aria-label="标记名称" placeholder="标记当前时刻" @keydown.enter.prevent="markRecording" />
                        <button type="button" :disabled="actionBusy" @click="markRecording"><Flag :size="13" />标记</button>
                        <button type="button" class="danger-text" :disabled="actionBusy" @click="stopRecording"><Square :size="12" />停止录制</button>
                    </div>
                </template>
                <template v-else>
                    <label class="compact-field"><span>目标</span>
                        <select v-model="recordingDraft.target_id" :disabled="actionBusy || !recordableTargets.length">
                            <option v-for="target in recordableTargets" :key="target.target_id" :value="target.target_id">{{ target.name }}</option>
                        </select>
                    </label>
                    <label class="compact-field"><span>策略</span>
                        <select v-model="recordingDraft.recording_mode" :disabled="actionBusy">
                            <option value="changed_frames">变化帧</option>
                            <option value="all_frames">全部帧</option>
                            <option value="diagnostic">诊断片段</option>
                        </select>
                    </label>
                    <button type="button" class="primary-action" :disabled="actionBusy || !recordingDraft.target_id" @click="startRecording">
                        <CircleDot :size="14" />开始录制
                    </button>
                    <p v-if="!recordableTargets.length" class="inline-note">开发端只能直接录制 Windows 或 ADB 目标；Android 本机录制请在手机 Player 的运行方案中开启。</p>
                    <details class="advanced-options">
                        <summary>资源保护</summary>
                        <label><span>帧率</span><input v-model.number="recordingDraft.target_fps" type="number" min="1" max="60" step="1" /><em>fps</em></label>
                        <label><span>最长</span><input v-model.number="maxMinutes" type="number" min="1" max="10080" step="1" /><em>分钟</em></label>
                        <label><span>空间上限</span><input v-model.number="maxGigabytes" type="number" min="0.1" max="1000" step="0.1" /><em>GiB</em></label>
                        <p>达到时长、空间或磁盘保护线时只停止录制，不停止任务。</p>
                    </details>
                </template>
                <p v-if="recording.last_error" class="inline-error" role="alert">{{ recording.last_error }}</p>
            </section>

            <div class="session-filters">
                <VNextListSearch v-model="searchText" placeholder="搜索目标或会话" aria-label="搜索录制会话" />
                <div>
                    <select v-model="targetFilter" aria-label="按目标筛选"><option value="">全部目标</option><option v-for="target in sessionTargets" :key="target" :value="target">{{ target }}</option></select>
                    <select v-model="statusFilter" aria-label="按状态筛选"><option value="">全部状态</option><option value="completed">已完成</option><option value="stopped">已停止</option><option value="error">异常</option></select>
                </div>
            </div>

            <VNextWorkspaceState v-if="rootBusy && !sessions.length" class="list-state" compact kind="loading" title="正在读取本机记录"><template #icon><LoaderCircle class="spin" :size="16" /></template></VNextWorkspaceState>
            <VNextWorkspaceState v-else-if="!filteredSessions.length" class="list-state" compact :kind="sessions.length ? 'filtered' : 'empty'" :title="sessions.length ? '没有符合条件的录制' : '还没有运行记录'" :description="sessions.length ? '清空筛选，或换一个关键词。' : '开始逐帧录制后，记录会保存在本机。'"><template #icon><Film :size="18" /></template></VNextWorkspaceState>
            <div v-else class="session-list app-navigation-list" role="listbox" aria-label="录制会话列表">
                <VNextNavigationItem
                    v-for="session in filteredSessions"
                    :key="session.session_id"
                    role="option"
                    density="multiline"
                    selectable
                    :selected="selectedSessionId === session.session_id"
                    @click="selectSession(session.session_id)"
                >
                    <span class="session-title"><strong>{{ session.target_title || session.target_id || '运行目标' }}</strong><em :data-tone="sessionTone(session)">{{ statusLabel(session.status, session.terminal_reason) }}</em></span>
                    <span>{{ formatDate(session.started_at) }} · {{ session.frame_count }} 帧 · {{ formatBytes(session.total_bytes) }}</span>
                    <span v-if="session.issue_count || session.dropped_frame_count" class="session-warning">{{ session.issue_count ? `${session.issue_count} 个完整性问题` : `${session.dropped_frame_count} 帧未保存` }}</span>
                </VNextNavigationItem>
            </div>
        </aside>

        <main class="replay-viewer" aria-label="录制帧查看器" :inert="sessionsOpen || detailOverlayOpen ? true : undefined" :aria-hidden="sessionsOpen || detailOverlayOpen ? 'true' : undefined">
            <template v-if="sessionDetail">
                <VNextPaneHeader class="viewer-header" role="workspace" :title="sessionDetail.target_title || '运行记录'" :meta="`${formatDate(sessionDetail.started_at)} · ${strategyLabel(sessionDetail.strategy)}`">
                    <template #actions><div class="viewer-actions">
                        <VNextButton size="compact" :disabled="!selectedFrame || actionBusy" @click="emitHistoryCapture"><template #icon><ScanLine /></template>历史帧采集</VNextButton>
                        <VNextButton size="compact" :disabled="actionBusy" @click="verifySession"><template #icon><ShieldCheck /></template>校验</VNextButton>
                        <VNextButton v-if="props.detailOpen === undefined" ref="inspectorToggle" class="inspector-toggle" size="compact" @click="openInspector"><template #icon><PanelRight /></template>检查器</VNextButton>
                    </div></template>
                </VNextPaneHeader>

                <div class="frame-stage" :aria-busy="frameBusy">
                    <div v-if="frameError" class="stage-state error" role="alert"><CircleAlert :size="20" /><strong>画面无法显示</strong><span>{{ frameError }}</span></div>
                    <div v-else-if="frameBusy && !frameUrl" class="stage-state"><LoaderCircle class="spin" :size="20" /><span>正在解码原始帧</span></div>
                    <img v-else-if="frameUrl" :src="frameUrl" :alt="`录制帧 ${selectedFrameSequence}`" draggable="false" />
                    <div v-else class="stage-state"><ImageOff :size="22" /><strong>选择一帧查看原始画面</strong></div>
                    <span v-if="frameUrl" class="source-badge">历史帧 · 不会重新截图</span>
                </div>

                <div class="playback-bar" aria-label="回放控制">
                    <button type="button" title="上一帧" aria-label="上一帧" :disabled="selectedFrameSequence <= 1" @click="stepFrame(-1)"><SkipBack :size="15" /></button>
                    <button type="button" :title="playing ? '暂停' : '播放'" :aria-label="playing ? '暂停' : '播放'" :disabled="!sessionDetail.frame_count" @click="togglePlayback">
                        <Pause v-if="playing" :size="15" /><Play v-else :size="15" />
                    </button>
                    <button type="button" title="下一帧" aria-label="下一帧" :disabled="selectedFrameSequence >= sessionDetail.frame_count" @click="stepFrame(1)"><SkipForward :size="15" /></button>
                    <label><span>帧</span><input v-model.number="jumpFrame" type="number" min="1" :max="sessionDetail.frame_count" @keydown.enter.prevent="jumpToFrame" /><button type="button" @click="jumpToFrame">跳转</button></label>
                    <select v-model.number="playbackSpeed" aria-label="播放速度"><option :value="0.5">0.5×</option><option :value="1">1×</option><option :value="2">2×</option><option :value="4">4×</option></select>
                    <span>{{ Math.max(0, selectedFrameSequence) }} / {{ sessionDetail.frame_count }}</span>
                </div>

                <section class="timeline-section" aria-label="虚拟化时间线">
                    <header><strong>时间线</strong><span>{{ timelineTotal }} 项 · 包含帧、标记与未保存区间</span></header>
                    <div ref="timelineViewport" class="timeline-viewport" tabindex="0" @scroll="onTimelineScroll" @keydown="onTimelineKeydown">
                        <div class="timeline-spacer" :style="{ height: `${timelineTotal * rowHeight}px` }">
                            <button
                                v-for="row in visibleTimelineRows"
                                :key="row.index"
                                type="button"
                                :class="['timeline-row', `kind-${row.item?.kind || 'loading'}`, { selected: row.item?.kind === 'frame' && row.item.sequence === selectedFrameSequence }]"
                                :style="{ transform: `translateY(${row.index * rowHeight}px)` }"
                                :disabled="!row.item"
                                @click="selectTimelineItem(row.item)"
                            >
                                <span class="timeline-glyph"><ImageIcon v-if="row.item?.kind === 'frame'" :size="13" /><Flag v-else-if="row.item?.kind === 'marker'" :size="13" /><Unplug v-else-if="row.item?.kind === 'drop'" :size="13" /><LoaderCircle v-else class="spin" :size="12" /></span>
                                <strong>{{ timelineLabel(row.item) }}</strong>
                                <span>{{ timelineMeta(row.item) }}</span>
                            </button>
                        </div>
                    </div>
                </section>
            </template>
            <VNextWorkspaceState v-else class="viewer-empty" kind="selection" title="选择一条运行记录" description="录制只保存在本机。选择会话后可以逐帧浏览、比较和运行无副作用分析。"><template #icon><Film :size="30" /></template></VNextWorkspaceState>
        </main>

        <aside
            v-if="detailVisible"
            ref="inspectorElement"
            :class="['replay-inspector', { 'is-open': inspectorOpen || detailOverlayOpen }]"
            aria-label="运行记录检查器"
            :role="detailOverlayOpen ? 'dialog' : undefined"
            :aria-modal="detailOverlayOpen ? 'true' : undefined"
            :tabindex="detailOverlayOpen ? -1 : undefined"
            @keydown="trapDialogFocus"
            @keydown.esc.stop.prevent="closeInspector"
        >
            <VNextPaneHeader class="pane-header" role="inspector" title="检查器" :meta="selectedFrame ? `帧 ${selectedFrame.sequence}` : '会话'"><template #actions><VNextIconButton class="quiet-icon inspector-close" data-dialog-initial-focus label="关闭检查器" @click="closeInspector"><X /></VNextIconButton></template></VNextPaneHeader>
            <div v-if="sessionDetail" class="inspector-scroll app-inspector-body app-inspector-form">
                <section v-if="verification" :class="['verification-result', { failed: !verification.ok }]">
                    <ShieldCheck v-if="verification.ok" :size="15" /><ShieldAlert v-else :size="15" />
                    <div><strong>{{ verification.ok ? '完整性校验通过' : '记录不完整，分析已阻止' }}</strong><span>{{ verification.verified_frame_count }} / {{ verification.frame_count }} 帧已验证</span></div>
                </section>

                <section class="inspector-section app-inspector-section">
                    <h2>当前帧</h2>
                    <dl v-if="selectedFrame" class="metadata-list">
                        <div><dt>采集时间</dt><dd>{{ formatTime(selectedFrame.captured_at) }}</dd></div>
                        <div><dt>画面</dt><dd>{{ selectedFrame.width }} × {{ selectedFrame.height }} · {{ orientationLabel(selectedFrame.orientation) }}</dd></div>
                        <div><dt>目标</dt><dd>{{ selectedFrame.target_title || selectedFrame.target_id }}</dd></div>
                    </dl>
                    <p v-else class="section-empty">时间线中选择一帧后显示真实元数据。</p>
                    <details v-if="selectedFrame" class="technical-frame-details app-inspector-disclosure">
                        <summary>技术信息</summary>
                        <dl class="metadata-list compact">
                            <div><dt>片段</dt><dd>{{ compactId(selectedFrame.recording_segment_id) }}</dd></div>
                            <div><dt>空间版本</dt><dd :title="selectedFrame.space_version">{{ selectedFrame.space_version }}</dd></div>
                            <div><dt>文件大小</dt><dd>{{ formatBytes(selectedFrame.bytes) }}</dd></div>
                        </dl>
                    </details>
                    <p class="section-help">可从当前帧取点、框选或录入图片，不会操作真实目标。</p>
                </section>

                <section class="inspector-section app-inspector-section">
                    <h2>像素比较</h2>
                    <div class="compare-inputs">
                        <label><span>左帧</span><input v-model.number="compareLeft" type="number" min="1" :max="sessionDetail.frame_count" /></label>
                        <label><span>右帧</span><input v-model.number="compareRight" type="number" min="1" :max="sessionDetail.frame_count" /></label>
                    </div>
                    <button type="button" class="app-inline-action" :disabled="actionBusy || !compareLeft || !compareRight" @click="compareFrames"><GitCompare :size="14" /><span>比较原始像素</span></button>
                    <template v-if="comparison">
                        <dl class="metadata-list compact">
                            <div><dt>变化像素</dt><dd>{{ formatPercent(comparison.changed_pixel_ratio) }}</dd></div>
                            <div><dt>平均通道差</dt><dd>{{ comparison.mean_channel_difference }}</dd></div>
                        </dl>
                        <img v-if="comparisonUrl" class="difference-preview" :src="comparisonUrl" alt="两帧像素差异图" />
                    </template>
                </section>

                <section class="inspector-section app-inspector-section">
                    <h2>无副作用分析</h2>
                    <p class="section-help">只重新执行图像与文字识别，不会产生点击、文件或网络操作。</p>
                    <div v-if="analysisCatalog.length" class="analysis-list">
                        <label v-for="analysis in analysisCatalog" :key="analysis.analysis_id"><input v-model="selectedAnalysisIds" type="checkbox" :value="analysis.analysis_id" /><span><strong>{{ analysis.display_name }}</strong><small>{{ analysis.owner_function_id }} · {{ compactId(analysis.statement_id) }}</small></span></label>
                    </div>
                    <p v-else-if="analysisUnavailableReason" class="section-empty analysis-unavailable" role="status">{{ analysisUnavailableReason }}</p>
                    <p v-else class="section-empty">当前入口没有可回放的官方图像或 OCR 语句。</p>
                    <div class="inline-actions">
                        <button type="button" class="app-inline-action" :disabled="analysisBusy || !selectedFrame || !selectedAnalysisIds.length" @click="analyzeCurrentFrame"><ScanSearch :size="14" /><span>分析当前帧</span></button>
                        <button type="button" class="app-inline-action" :disabled="analysisBusy || !selectedAnalysisIds.length" @click="analyzeWholeSession"><ScanLine :size="14" /><span>分析会话</span></button>
                    </div>
                    <p v-if="analysisMessage" class="analysis-result" role="status">{{ analysisMessage }}</p>
                    <details v-if="reports.length" class="report-history app-inspector-disclosure">
                        <summary>分析历史 · {{ reports.length }}</summary>
                        <div v-for="report in reports" :key="report.analysis_run_id" class="report-row">
                            <span><strong>{{ formatDate(report.created_at) }}</strong><small>{{ compactId(report.analysis_run_id) }} · {{ report.reproducibility }}</small></span>
                            <button type="button" title="删除报告" aria-label="删除分析报告" @click="deleteReport(report.analysis_run_id)"><Trash2 :size="13" /></button>
                        </div>
                    </details>
                </section>

                <section class="inspector-section app-inspector-section">
                    <h2>导出</h2>
                    <label class="choice-row"><input v-model="exportMode" type="radio" value="default" /><span><strong>画面与报告</strong><small>包含所选范围的敏感画面、时间线、报告与校验清单；不包含项目逻辑、ECIR、资源或分析输入快照。</small></span></label>
                    <label class="choice-row"><input v-model="exportMode" type="radio" value="reproducible" /><span><strong>可重现分析包</strong><small>除画面外，逐类加入你明确选择的分析依赖。</small></span></label>
                    <label class="compact-field export-scope"><span>画面范围</span><select v-model="exportScope"><option value="current">当前帧</option><option value="all">整个会话</option></select></label>
                    <div v-if="exportMode === 'reproducible'" class="privacy-categories">
                        <label v-for="category in exportCategories" :key="category.id"><input v-model="selectedExportCategories" type="checkbox" :value="category.id" /><span><strong>{{ category.label }}</strong><small>{{ category.description }}</small></span></label>
                    </div>
                    <p class="privacy-warning"><LockKeyhole :size="13" />不会自动上传。画面可能包含账号、聊天或其他敏感内容。</p>
                    <button type="button" class="app-inline-action" :disabled="exportBusy || (exportScope === 'current' && !selectedFrame) || (exportMode === 'reproducible' && !selectedExportCategories.length)" @click="exportSession"><Download :size="14" /><span>检查清单并导出</span></button>
                </section>

                <section class="inspector-section app-inspector-section danger-zone">
                    <h2>本机数据</h2>
                    <template v-if="!deleteArmed"><button type="button" class="danger-outline" @click="deleteArmed = true"><Trash2 :size="14" />删除这条录制</button></template>
                    <div v-else class="delete-confirm" role="alert">
                        <strong>确认删除本机会话？</strong>
                        <span>将释放约 {{ formatBytes(sessionDetail.total_bytes) }}。活动、锁定或仍被报告引用的会话会由后端阻止。</span>
                        <div><button type="button" @click="deleteArmed = false">取消</button><button type="button" class="danger-solid" :disabled="actionBusy" @click="deleteSession">删除录制</button></div>
                    </div>
                </section>

                <VNextInlineNotice v-if="workspaceError" class="workspace-error" tone="error" :message="workspaceError" />
            </div>
            <VNextWorkspaceState v-else class="inspector-empty" compact kind="selection" title="选择运行记录" description="随后可检查元数据、比较、分析和导出。" />
        </aside>
    </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import {
    CircleAlert, CircleDot, Download, Film, Flag, GitCompare, Image as ImageIcon, ImageOff,
    LoaderCircle, LockKeyhole, PanelLeft, PanelRight, Pause, Play, RefreshCw, ScanLine, ScanSearch, ShieldAlert,
    ShieldCheck, SkipBack, SkipForward, Square, Trash2, Unplug, X,
} from 'lucide-vue-next'
import { replayApi } from '../replayApi'
import type {
    RecordingStartOptions, RecordingState, ReplayAnalysisCatalogItem, ReplayAnalysisReport,
    ReplayComparison, ReplayFrame, ReplaySessionDetail, ReplaySessionSummary, ReplayTimelineItem,
    ReplayVerification,
} from '../replayTypes'
import { useVNextStore } from '../store'
import VNextPaneHeader from './ui/VNextPaneHeader.vue'
import VNextListSearch from './ui/VNextListSearch.vue'
import VNextWorkspaceState from './ui/VNextWorkspaceState.vue'
import VNextInlineNotice from './ui/VNextInlineNotice.vue'
import VNextButton from './ui/VNextButton.vue'
import VNextIconButton from './ui/VNextIconButton.vue'
import VNextNavigationItem from './ui/VNextNavigationItem.vue'
import { trapDialogFocus, useDialogFocusReturn } from '../dialogFocus'

const props = withDefaults(defineProps<{ detailOpen?: boolean; detailOverlay?: boolean }>(), { detailOpen: undefined, detailOverlay: undefined })
const emit = defineEmits<{
    (event: 'open-history-frame', sessionId: string, frameIndex: number): void
    (event: 'update:detail-open', open: boolean): void
}>()
const store = useVNextStore()
const emptyRecording = (): RecordingState => ({ active: false, status: 'idle', session_id: '', strategy: 'changed_frames', frame_count: 0, capture_count: 0, dropped_frame_count: 0, policy_skipped_frame_count: 0, disk_bytes: 0, elapsed_ms: 0, terminal_reason: '', last_error: '', target_id: '', target_title: '' })
const sessions = ref<ReplaySessionSummary[]>([])
const sessionDetail = ref<ReplaySessionDetail | null>(null)
const selectedSessionId = ref('')
const selectedFrame = ref<ReplayFrame | null>(null)
const selectedFrameSequence = ref(0)
const frameUrl = ref('')
const comparisonUrl = ref('')
const frameBusy = ref(false)
const frameError = ref('')
const rootBusy = ref(false)
const actionBusy = ref(false)
const analysisBusy = ref(false)
const exportBusy = ref(false)
const workspaceError = ref('')
const recording = ref<RecordingState>(emptyRecording())
const markerLabel = ref('')
const searchText = ref('')
const targetFilter = ref('')
const statusFilter = ref('')
const maxMinutes = ref(30)
const maxGigabytes = ref(2)
const recordingDraft = ref<RecordingStartOptions>({ target_id: '', target_fps: 15, queue_capacity: 48, recording_mode: 'changed_frames', change_threshold: 0.006, max_duration_ms: 1_800_000, max_session_bytes: 2_147_483_648, min_free_bytes: 536_870_912, diagnostic_pre_frames: 45, diagnostic_post_frames: 20 })
const timelineRows = ref<Array<ReplayTimelineItem | undefined>>([])
const timelineTotal = ref(0)
const timelineScrollTop = ref(0)
const timelineViewport = ref<HTMLElement | null>(null)
const rowHeight = 38
const viewportRows = 12
const timelineRequests = new Set<number>()
const frameRows = new Map<number, ReplayFrame>()
const framePageRequests = new Set<number>()
const playing = ref(false)
const playbackSpeed = ref(1)
const jumpFrame = ref(1)
const compareLeft = ref(1)
const compareRight = ref(1)
const comparison = ref<ReplayComparison | null>(null)
const verification = ref<ReplayVerification | null>(null)
const analysisCatalog = ref<ReplayAnalysisCatalogItem[]>([])
const analysisUnavailableReason = ref('')
const selectedAnalysisIds = ref<string[]>([])
const reports = ref<ReplayAnalysisReport[]>([])
const analysisMessage = ref('')
const exportMode = ref<'default' | 'reproducible'>('default')
const exportScope = ref<'current' | 'all'>('current')
const selectedExportCategories = ref<string[]>([])
const deleteArmed = ref(false)
const inspectorOpen = ref(false)
const detailVisible = computed(() => props.detailOpen ?? true)
const detailOverlayOpen = computed(() => detailVisible.value && (props.detailOverlay ?? inspectorOpen.value))
const sessionsOpen = ref(false)
const sessionsElement = ref<HTMLElement | null>(null)
const inspectorElement = ref<HTMLElement | null>(null)
const sessionsToggle = ref<InstanceType<typeof VNextIconButton> | null>(null)
const inspectorToggle = ref<InstanceType<typeof VNextButton> | null>(null)
let statusTimer: ReturnType<typeof setTimeout> | null = null
let playbackTimer: ReturnType<typeof setTimeout> | null = null
let frameAbort: AbortController | null = null
let compareAbort: AbortController | null = null
let loadGeneration = 0

const exportCategories = [
    { id: 'program', label: '项目函数', description: '规范化 ProgramDocument，可能包含业务逻辑。' },
    { id: 'ecir', label: 'ECIR', description: '本次分析使用的确定性编译产物。' },
    { id: 'resources', label: '图片资源', description: '分析实际引用的原始资源字节。' },
    { id: 'ocr', label: 'OCR 依赖', description: '模型、字典和引擎版本。' },
    { id: 'parameters', label: '参数与锁文件', description: '分析参数和 easycode.lock，可能包含路径或配置。' },
    { id: 'implementation', label: '官方实现', description: '对应的官方回放适配器与契约字节。' },
]

const workspace = computed(() => store.workspace)

useDialogFocusReturn(sessionsOpen, sessionsElement)
async function openInspector(): Promise<void> {
    inspectorOpen.value = true
    emit('update:detail-open', true)
    await nextTick()
    inspectorElement.value?.querySelector<HTMLElement>('[data-dialog-initial-focus]')?.focus()
}

async function closeInspector(): Promise<void> {
    inspectorOpen.value = false
    emit('update:detail-open', false)
    await nextTick()
    inspectorToggle.value?.focus()
}

function closeOverlays(): void {
    sessionsOpen.value = false
    if (inspectorOpen.value || detailOverlayOpen.value) void closeInspector()
}
const recordableTargets = computed(() => store.targets.filter(target => target.type === 'windows' || target.type === 'android_adb'))
const sessionTargets = computed(() => [...new Set(sessions.value.map(item => item.target_title || item.target_id).filter(Boolean))])
const filteredSessions = computed(() => {
    const query = searchText.value.trim().toLocaleLowerCase()
    return sessions.value.filter(item => {
        const target = item.target_title || item.target_id
        return (!query || `${target} ${item.session_id}`.toLocaleLowerCase().includes(query))
            && (!targetFilter.value || target === targetFilter.value)
            && (!statusFilter.value || item.status === statusFilter.value)
    })
})
const recordingSummary = computed(() => recording.value.active
    ? `${strategyLabel(recording.value.strategy)} · ${formatDuration(recording.value.elapsed_ms)}`
    : '默认关闭，只录制当前目标工作区')
const firstVisibleTimeline = computed(() => Math.max(0, Math.floor(timelineScrollTop.value / rowHeight) - 4))
const visibleTimelineRows = computed(() => {
    const start = firstVisibleTimeline.value
    const end = Math.min(timelineTotal.value, start + viewportRows + 8)
    return Array.from({ length: Math.max(0, end - start) }, (_, index) => ({ index: start + index, item: timelineRows.value[start + index] }))
})

function message(error: unknown): string { return error instanceof Error ? error.message : String(error || '操作失败') }
function formatBytes(value: number): string { const bytes = Math.max(0, Number(value || 0)); if (bytes < 1024) return `${bytes} B`; if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KiB`; if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MiB`; return `${(bytes / 1024 ** 3).toFixed(2)} GiB` }
function formatDate(value: string): string { if (!value) return '时间未知'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(date) }
function formatTime(value: string): string { if (!value) return '未知'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit', fractionalSecondDigits: 3 }).format(date) }
function formatDuration(value: number): string { const seconds = Math.max(0, Math.floor(Number(value || 0) / 1000)); const minutes = Math.floor(seconds / 60); return `${String(minutes).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}` }
function formatPercent(value: number): string { return `${(Number(value || 0) * 100).toFixed(2)}%` }
function compactId(value: string): string { return value.length > 20 ? `${value.slice(0, 9)}…${value.slice(-7)}` : value || '—' }
function strategyLabel(value: string): string { return ({ all_frames: '全部帧', changed_frames: '变化帧', diagnostic: '诊断片段' } as Record<string, string>)[value] || value || '未知策略' }
function orientationLabel(value: string): string { return ({ portrait: '竖屏', landscape: '横屏', square: '方形' } as Record<string, string>)[value] || value || '方向未知' }
function statusLabel(status: string, reason: string): string { if (reason === 'process_interrupted') return '进程中断'; if (status === 'completed') return '已完成'; if (status === 'stopped') return '已停止'; if (status === 'recording' || status === 'starting') return '录制中'; if (status === 'error') return '异常'; return status || '未知' }
function sessionTone(session: ReplaySessionSummary): string { return session.status === 'error' || session.issue_count ? 'danger' : session.status === 'recording' ? 'active' : 'neutral' }
function releaseUrl(kind: 'frame' | 'comparison'): void { const current = kind === 'frame' ? frameUrl.value : comparisonUrl.value; if (current) URL.revokeObjectURL(current); if (kind === 'frame') frameUrl.value = ''; else comparisonUrl.value = '' }

async function refreshAll(): Promise<void> {
    if (!workspace.value) return
    const generation = ++loadGeneration
    rootBusy.value = true
    workspaceError.value = ''
    try {
        const [nextSessions, nextStatus] = await Promise.all([replayApi.sessions(workspace.value), replayApi.status(workspace.value)])
        if (generation !== loadGeneration) return
        sessions.value = nextSessions
        recording.value = nextStatus
        if (!recordingDraft.value.target_id && recordableTargets.value.length) recordingDraft.value.target_id = store.defaultTargetId && recordableTargets.value.some(item => item.target_id === store.defaultTargetId) ? store.defaultTargetId : recordableTargets.value[0].target_id
        if (selectedSessionId.value && !nextSessions.some(item => item.session_id === selectedSessionId.value)) clearSession()
        if (!selectedSessionId.value && nextSessions.length) await selectSession(nextSessions[0].session_id)
        scheduleStatusPoll()
    } catch (error) { if (generation === loadGeneration) workspaceError.value = message(error) }
    finally { if (generation === loadGeneration) rootBusy.value = false }
    if (!sessions.value.length) {
        analysisCatalog.value = []
        analysisUnavailableReason.value = ''
        selectedAnalysisIds.value = []
        return
    }
    try {
        if (!workspace.value) return
        const catalog = await replayApi.catalog(workspace.value)
        analysisCatalog.value = catalog.analyses
        analysisUnavailableReason.value = catalog.available ? '' : catalog.unavailable_reason
        selectedAnalysisIds.value = analysisCatalog.value.map(item => item.analysis_id)
    } catch (error) {
        analysisCatalog.value = []
        analysisUnavailableReason.value = message(error)
        selectedAnalysisIds.value = []
    }
}

function clearSession(): void {
    playing.value = false
    selectedSessionId.value = ''
    sessionDetail.value = null
    selectedFrame.value = null
    selectedFrameSequence.value = 0
    timelineRows.value = []
    timelineTotal.value = 0
    frameRows.clear()
    reports.value = []
    verification.value = null
    comparison.value = null
    releaseUrl('frame'); releaseUrl('comparison')
}

async function selectSession(sessionId: string): Promise<void> {
    if (!workspace.value || !sessionId) return
    if (typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 700px)').matches) sessionsOpen.value = false
    const generation = ++loadGeneration
    selectedSessionId.value = sessionId
    sessionDetail.value = null
    selectedFrame.value = null
    selectedFrameSequence.value = 0
    timelineRows.value = []
    timelineTotal.value = 0
    timelineRequests.clear(); frameRows.clear(); framePageRequests.clear()
    reports.value = []; verification.value = null; comparison.value = null; deleteArmed.value = false
    releaseUrl('frame'); releaseUrl('comparison')
    rootBusy.value = true; workspaceError.value = ''
    try {
        const [detail, nextReports] = await Promise.all([replayApi.session(workspace.value, sessionId), replayApi.reports(workspace.value, sessionId)])
        if (generation !== loadGeneration || selectedSessionId.value !== sessionId) return
        sessionDetail.value = detail; reports.value = nextReports
        timelineTotal.value = detail.frame_count + detail.marker_count + detail.drop_event_count
        timelineRows.value = new Array(timelineTotal.value)
        compareLeft.value = 1; compareRight.value = Math.min(2, Math.max(1, detail.frame_count)); jumpFrame.value = 1
        await Promise.all([ensureTimelineRange(0, 80), ensureFrame(1)])
        if (detail.frame_count) await selectFrameSequenceValue(1)
    } catch (error) { if (generation === loadGeneration) workspaceError.value = message(error) }
    finally { if (generation === loadGeneration) rootBusy.value = false }
}

async function ensureTimelineRange(start: number, end: number): Promise<void> {
    if (!workspace.value || !selectedSessionId.value || !timelineTotal.value) return
    const pageSize = 300
    const first = Math.floor(Math.max(0, start) / pageSize) * pageSize
    const last = Math.floor(Math.max(0, end - 1) / pageSize) * pageSize
    const pages: Promise<void>[] = []
    for (let offset = first; offset <= last; offset += pageSize) {
        if (timelineRequests.has(offset) || timelineRows.value[offset]) continue
        timelineRequests.add(offset)
        pages.push(replayApi.timeline(workspace.value, selectedSessionId.value, offset, pageSize).then(result => {
            timelineTotal.value = result.total
            if (timelineRows.value.length !== result.total) timelineRows.value.length = result.total
            result.items.forEach((item, index) => { timelineRows.value[result.offset + index] = item })
        }).finally(() => timelineRequests.delete(offset)))
    }
    await Promise.all(pages)
}

async function ensureFrame(sequence: number): Promise<ReplayFrame | null> {
    if (!workspace.value || !selectedSessionId.value || sequence < 1) return null
    if (frameRows.has(sequence)) return frameRows.get(sequence) || null
    const pageSize = 200
    const offset = Math.floor((sequence - 1) / pageSize) * pageSize
    if (!framePageRequests.has(offset)) {
        framePageRequests.add(offset)
        try {
            const result = await replayApi.frames(workspace.value, selectedSessionId.value, offset, pageSize)
            result.frames.forEach(frame => frameRows.set(frame.sequence || 0, frame))
        } finally { framePageRequests.delete(offset) }
    }
    return frameRows.get(sequence) || null
}

async function selectFrameSequenceValue(sequence: number): Promise<void> {
    if (!workspace.value || !sessionDetail.value) return
    const bounded = Math.max(1, Math.min(sessionDetail.value.frame_count, Math.floor(sequence)))
    const frame = await ensureFrame(bounded)
    if (!frame) { frameError.value = `帧 ${bounded} 的索引不存在`; return }
    selectedFrame.value = frame; selectedFrameSequence.value = bounded; jumpFrame.value = bounded
    if (!compareLeft.value) compareLeft.value = bounded
    frameAbort?.abort(); frameAbort = new AbortController(); frameBusy.value = true; frameError.value = ''; releaseUrl('frame')
    try {
        const blob = await replayApi.frameBlob(workspace.value, selectedSessionId.value, bounded, frameAbort.signal)
        frameUrl.value = URL.createObjectURL(blob)
    } catch (error) { if ((error as { name?: string })?.name !== 'AbortError') frameError.value = message(error) }
    finally { frameBusy.value = false }
}

function selectTimelineItem(item?: ReplayTimelineItem): void { if (item?.kind === 'frame') void selectFrameSequenceValue(item.sequence) }
function timelineLabel(item?: ReplayTimelineItem): string { if (!item) return '正在载入'; if (item.kind === 'frame') return `帧 ${item.sequence}`; if (item.kind === 'marker') return item.label || '标记'; return `${item.count} 帧未保存` }
function timelineMeta(item?: ReplayTimelineItem): string { if (!item) return ''; if (item.kind === 'frame') return `${formatTime(item.captured_at)} · 变化 ${(item.change_score * 100).toFixed(1)}%`; if (item.kind === 'marker') return formatTime(item.marked_at); return `${item.start_capture_sequence}–${item.end_capture_sequence} · ${item.reason}` }
function onTimelineScroll(event: Event): void { timelineScrollTop.value = (event.currentTarget as HTMLElement).scrollTop; void ensureTimelineRange(firstVisibleTimeline.value, firstVisibleTimeline.value + viewportRows + 12) }
function onTimelineKeydown(event: KeyboardEvent): void { if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') { event.preventDefault(); void stepFrame(-1) } else if (event.key === 'ArrowRight' || event.key === 'ArrowDown') { event.preventDefault(); void stepFrame(1) } else if (event.key === ' ') { event.preventDefault(); togglePlayback() } }
async function stepFrame(delta: number): Promise<void> { if (!sessionDetail.value) return; await selectFrameSequenceValue(Math.max(1, Math.min(sessionDetail.value.frame_count, selectedFrameSequence.value + delta))) }
function jumpToFrame(): void { void selectFrameSequenceValue(jumpFrame.value) }
function togglePlayback(): void { playing.value = !playing.value; if (playing.value) schedulePlayback() }
function schedulePlayback(): void { if (playbackTimer) clearTimeout(playbackTimer); if (!playing.value || !sessionDetail.value) return; if (selectedFrameSequence.value >= sessionDetail.value.frame_count) { playing.value = false; return } playbackTimer = setTimeout(async () => { await stepFrame(1); schedulePlayback() }, Math.max(100, 1000 / playbackSpeed.value)) }

function scheduleStatusPoll(): void { if (statusTimer) clearTimeout(statusTimer); statusTimer = null; if (!recording.value.active || !workspace.value) return; statusTimer = setTimeout(async () => { if (!workspace.value) return; try { const before = recording.value.active; recording.value = await replayApi.status(workspace.value); if (before && !recording.value.active) await refreshAll() } catch (error) { workspaceError.value = message(error) } finally { scheduleStatusPoll() } }, 1000) }
async function startRecording(): Promise<void> { if (!workspace.value) return; actionBusy.value = true; workspaceError.value = ''; try { recordingDraft.value.max_duration_ms = Math.round(maxMinutes.value * 60_000); recordingDraft.value.max_session_bytes = Math.round(maxGigabytes.value * 1024 ** 3); recording.value = await replayApi.start(workspace.value, recordingDraft.value); scheduleStatusPoll(); await refreshAll() } catch (error) { workspaceError.value = message(error) } finally { actionBusy.value = false } }
async function stopRecording(): Promise<void> { if (!workspace.value) return; actionBusy.value = true; try { recording.value = await replayApi.stop(workspace.value); await refreshAll() } catch (error) { workspaceError.value = message(error) } finally { actionBusy.value = false } }
async function markRecording(): Promise<void> { if (!workspace.value || !recording.value.active) return; actionBusy.value = true; try { await replayApi.mark(workspace.value, markerLabel.value.trim() || '手动标记'); markerLabel.value = '' } catch (error) { workspaceError.value = message(error) } finally { actionBusy.value = false } }
function emitHistoryCapture(): void { if (selectedFrame.value && selectedSessionId.value) emit('open-history-frame', selectedSessionId.value, selectedFrame.value.sequence) }

async function verifySession(): Promise<void> { if (!workspace.value || !selectedSessionId.value) return; actionBusy.value = true; try { verification.value = await replayApi.verify(workspace.value, selectedSessionId.value) } catch (error) { workspaceError.value = message(error) } finally { actionBusy.value = false } }
async function compareFrames(): Promise<void> { if (!workspace.value || !selectedSessionId.value) return; actionBusy.value = true; comparison.value = null; releaseUrl('comparison'); compareAbort?.abort(); compareAbort = new AbortController(); try { comparison.value = await replayApi.compare(workspace.value, selectedSessionId.value, compareLeft.value, compareRight.value); const blob = await replayApi.comparisonBlob(workspace.value, selectedSessionId.value, compareLeft.value, compareRight.value, compareAbort.signal); comparisonUrl.value = URL.createObjectURL(blob) } catch (error) { if ((error as { name?: string })?.name !== 'AbortError') workspaceError.value = message(error) } finally { actionBusy.value = false } }
async function analyzeCurrentFrame(): Promise<void> { if (!workspace.value || !selectedFrame.value) return; analysisBusy.value = true; analysisMessage.value = ''; try { const result = await replayApi.analyzeFrame(workspace.value, selectedSessionId.value, selectedFrame.value.sequence, selectedAnalysisIds.value); analysisMessage.value = `分析已保存：${String(result.analysis_run_id || '')}`; reports.value = await replayApi.reports(workspace.value, selectedSessionId.value) } catch (error) { workspaceError.value = message(error) } finally { analysisBusy.value = false } }
async function analyzeWholeSession(): Promise<void> { if (!workspace.value) return; analysisBusy.value = true; analysisMessage.value = ''; try { const result = await replayApi.analyzeSession(workspace.value, selectedSessionId.value, selectedAnalysisIds.value); analysisMessage.value = `会话分析已保存：${String(result.analysis_run_id || '')}`; reports.value = await replayApi.reports(workspace.value, selectedSessionId.value) } catch (error) { workspaceError.value = message(error) } finally { analysisBusy.value = false } }
async function deleteReport(analysisRunId: string): Promise<void> { if (!workspace.value) return; try { await replayApi.deleteReport(workspace.value, selectedSessionId.value, analysisRunId); reports.value = await replayApi.reports(workspace.value, selectedSessionId.value) } catch (error) { workspaceError.value = message(error) } }
async function exportSession(): Promise<void> { if (!workspace.value) return; exportBusy.value = true; workspaceError.value = ''; try { const frameIndices = exportScope.value === 'current' && selectedFrame.value ? [selectedFrame.value.sequence] : []; const result = await replayApi.createExport(workspace.value, selectedSessionId.value, exportMode.value, reports.value.map(item => item.analysis_run_id), selectedExportCategories.value, frameIndices); const blob = await replayApi.exportBlob(workspace.value, selectedSessionId.value, result.export_id); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = `${selectedSessionId.value}-${result.mode}.zip`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 0) } catch (error) { workspaceError.value = message(error) } finally { exportBusy.value = false } }
async function deleteSession(): Promise<void> { if (!workspace.value) return; actionBusy.value = true; try { await replayApi.deleteSession(workspace.value, selectedSessionId.value); clearSession(); await refreshAll() } catch (error) { workspaceError.value = message(error) } finally { actionBusy.value = false } }

watch(() => workspace.value ? `${workspace.value.workspace_id}:${workspace.value.generation}` : '', async () => { clearSession(); if (workspace.value) await nextTick(refreshAll) }, { immediate: true })
watch(recordableTargets, targets => { if (!recordingDraft.value.target_id && targets.length) recordingDraft.value.target_id = targets[0].target_id }, { immediate: true })
watch(playbackSpeed, () => { if (playing.value) schedulePlayback() })
onBeforeUnmount(() => { loadGeneration += 1; if (statusTimer) clearTimeout(statusTimer); if (playbackTimer) clearTimeout(playbackTimer); frameAbort?.abort(); compareAbort?.abort(); releaseUrl('frame'); releaseUrl('comparison') })
</script>

<style scoped>
.replay-workspace.detail-panel-collapsed { grid-template-columns: minmax(238px, 280px) minmax(420px, 1fr); }
.replay-workspace { width: 100%; height: 100%; min-width: 0; min-height: 0; display: grid; grid-template-columns: minmax(238px, 280px) minmax(420px, 1fr) minmax(300px, 360px); overflow: hidden; background: var(--app-bg-base); color: var(--app-text-regular); }
.replay-sessions, .replay-inspector { min-width: 0; min-height: 0; background: var(--app-bg-sidebar); }
.replay-sessions { display: grid; grid-template-rows: var(--app-height-pane-header) auto auto minmax(0, 1fr); border-right: 1px solid var(--app-border-subtle); }
.replay-inspector { display: grid; grid-template-rows: var(--app-height-pane-header) minmax(0, 1fr); border-left: 1px solid var(--app-border-subtle); }
.pane-header { min-height: var(--app-height-pane-header); display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 0 10px 0 12px; border-bottom: 1px solid var(--app-border-subtle); }
.pane-header > div { min-width: 0; display: flex; align-items: baseline; gap: 7px; }
.pane-header strong { color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; }
.pane-header small { color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
button, input, select { font: inherit; }
button:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible { outline: 0; box-shadow: var(--focus-ring); }
button:disabled { cursor: not-allowed; opacity: .45; }
.quiet-icon { width: 28px; height: var(--app-control-compact); display: grid; place-items: center; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); cursor: pointer; }
.inspector-close, .inspector-toggle, .sessions-close, .sessions-toggle, .replay-scrim { display: none !important; }
.pane-header-actions { flex: none; display: flex; align-items: center; gap: 2px; }
.quiet-icon:hover:not(:disabled) { background: var(--app-bg-hover); color: var(--app-text-primary); }
.recording-strip { display: flex; flex-direction: column; gap: 9px; padding: 11px 12px 12px; border-bottom: 1px solid var(--app-border-subtle); }
.recording-heading { display: flex; align-items: center; gap: 8px; }
.recording-heading > div { min-width: 0; display: flex; flex-direction: column; }
.recording-heading strong { color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; }
.recording-heading small { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--app-text-disabled); }
.status-dot.active { background: var(--app-color-danger); box-shadow: 0 0 0 3px var(--app-color-danger-soft); }
.compact-field { display: grid; grid-template-columns: 44px minmax(0, 1fr); align-items: center; gap: 7px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.compact-field input, .compact-field select, .recording-actions input, .session-filters input, .session-filters select, .playback-bar input, .playback-bar select, .compare-inputs input { min-width: 0; height: var(--app-control-default); padding: 0 8px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); outline: 0; background: var(--app-bg-input); color: var(--app-text-primary); }
.compact-field input:focus, .compact-field select:focus, .recording-actions input:focus, .session-filters input:focus, .session-filters select:focus, .playback-bar input:focus, .playback-bar select:focus, .compare-inputs input:focus { border-color: var(--app-color-primary); }
.primary-action, .recording-actions button, .viewer-actions button, .inline-actions button:not(.app-inline-action), .playback-bar button { min-height: var(--app-control-default); display: inline-flex; align-items: center; justify-content: center; gap: 5px; padding: 0 9px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-raised); color: var(--app-text-regular); cursor: pointer; }
.primary-action { border-color: var(--app-color-primary); background: var(--app-color-primary); color: var(--app-color-on-primary); }
.primary-action:hover:not(:disabled), .recording-actions button:hover:not(:disabled), .viewer-actions button:hover:not(:disabled), .inline-actions button:not(.app-inline-action):hover:not(:disabled), .playback-bar button:hover:not(:disabled) { border-color: var(--app-border-strong); background: var(--app-bg-hover); color: var(--app-text-primary); }
.recording-actions { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px; }
.recording-actions .danger-text { grid-column: 1 / -1; color: var(--app-color-danger); }
.live-stats { display: grid; grid-template-columns: repeat(3, 1fr); margin: 1px 0; }
.live-stats div { min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.live-stats dt { color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.live-stats dd { margin: 0; color: var(--app-text-primary); font-size: var(--app-font-xs); }
.inline-note, .advanced-options p, .section-help { margin: 0; color: var(--app-text-placeholder); font-size: var(--app-font-xs); line-height: 1.55; }
.inline-error, .workspace-error { margin: 0; color: var(--app-color-danger); font-size: var(--app-font-xs); line-height: 1.5; }
.advanced-options { font-size: var(--app-font-xs); }
.advanced-options summary { width: max-content; color: var(--app-text-secondary); cursor: pointer; }
.advanced-options[open] summary { margin-bottom: 7px; }
.advanced-options label { display: grid; grid-template-columns: 72px minmax(0, 1fr) 36px; align-items: center; gap: 6px; margin: 6px 0; color: var(--app-text-secondary); }
.advanced-options input { min-width: 0; height: var(--app-control-default); padding: 0 7px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-input); color: var(--app-text-primary); }
.advanced-options em { color: var(--app-text-placeholder); font-style: normal; }
.session-filters { display: flex; flex-direction: column; gap: 7px; padding: 9px 8px; border-bottom: 1px solid var(--app-border-subtle); }
.search-field { height: var(--app-control-compact); display: flex; align-items: center; gap: 6px; padding: 0 7px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); color: var(--app-text-placeholder); background: var(--app-bg-input); }
.search-field input { width: 100%; height: 24px; padding: 0; border: 0; background: transparent; }
.search-field:focus-within { border-color: var(--app-color-primary); box-shadow: var(--focus-ring); }
.session-filters > div { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.session-filters select { width: 100%; }
.session-list { min-height: 0; overflow: auto; padding: 5px; }
.session-list > button { width: 100%; min-height: var(--app-list-row-multiline); display: flex; flex-direction: column; align-items: stretch; justify-content: center; gap: 2px; padding: 5px 8px; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); font: inherit; font-size: var(--app-font-xs); text-align: start; cursor: pointer; }
.session-list > button:hover { background: var(--app-bg-hover); }
.session-title { display: flex; align-items: center; justify-content: space-between; gap: 7px; }
.session-title strong { min-width: 0; overflow: hidden; color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.session-title em { flex: none; padding: 1px 5px; border-radius: 999px; background: var(--app-bg-raised); color: var(--app-text-secondary); font-style: normal; }
.session-title em[data-tone="danger"], .session-warning { color: var(--app-color-danger); }
.session-title em[data-tone="active"] { color: var(--app-color-success); }
.session-warning { font-size: var(--app-font-xs); }
.list-state, .viewer-empty, .inspector-empty { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 7px; padding: 20px; color: var(--app-text-secondary); font-size: var(--app-font-sm); text-align: center; }
.replay-viewer { min-width: 0; min-height: 0; display: grid; grid-template-rows: var(--app-height-workspace-header) minmax(220px, 1fr) 42px minmax(142px, 31%); overflow: hidden; background: var(--app-canvas-bg); }
.viewer-header { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 0 10px 0 13px; border-bottom: 1px solid var(--app-border-subtle); }
.viewer-header > div:first-child { min-width: 0; display: flex; flex-direction: column; }
.viewer-header strong { overflow: hidden; color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.viewer-header span { color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.viewer-actions { flex: none; display: flex; gap: 6px; }
.frame-stage { position: relative; min-width: 0; min-height: 0; display: grid; place-items: center; overflow: auto; padding: 16px; background-color: var(--app-bg-base); background-image: linear-gradient(45deg, var(--app-bg-panel) 25%, transparent 25%), linear-gradient(-45deg, var(--app-bg-panel) 25%, transparent 25%), linear-gradient(45deg, transparent 75%, var(--app-bg-panel) 75%), linear-gradient(-45deg, transparent 75%, var(--app-bg-panel) 75%); background-position: 0 0, 0 6px, 6px -6px, -6px 0; background-size: 12px 12px; }
.frame-stage img { display: block; max-width: 100%; max-height: 100%; object-fit: contain; image-rendering: auto; box-shadow: var(--app-shadow-lg); }
.source-badge { position: absolute; inset: 10px auto auto 10px; padding: 3px 7px; border: 1px solid var(--app-border-default); border-radius: 999px; background: var(--app-bg-raised); color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.stage-state { display: flex; flex-direction: column; align-items: center; gap: 7px; color: var(--app-text-secondary); text-align: center; }
.stage-state strong { color: var(--app-text-primary); }
.stage-state.error { color: var(--app-color-danger); }
.playback-bar { display: flex; align-items: center; gap: 6px; padding: 0 10px; border-top: 1px solid var(--app-border-subtle); border-bottom: 1px solid var(--app-border-subtle); background: var(--app-bg-chrome); }
.playback-bar > button { width: 28px; padding: 0; }
.playback-bar label { display: flex; align-items: center; gap: 5px; margin-left: 6px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.playback-bar input { width: 64px; }
.playback-bar select { width: 64px; margin-left: auto; }
.playback-bar > span { min-width: 62px; color: var(--app-text-secondary); font-size: var(--app-font-xs); text-align: end; }
.timeline-section { min-width: 0; min-height: 0; display: grid; grid-template-rows: 32px minmax(0, 1fr); }
.timeline-section > header { display: flex; align-items: center; gap: 8px; padding: 0 11px; }
.timeline-section > header strong { color: var(--app-text-primary); font-size: var(--app-font-xs); }
.timeline-section > header span { color: var(--app-text-placeholder); font-size: var(--app-font-xs); }
.timeline-viewport { min-height: 0; overflow: auto; outline: 0; }
.timeline-spacer { position: relative; min-width: 100%; }
.timeline-row { position: absolute; inset: 0 0 auto 0; width: 100%; height: 38px; display: grid; grid-template-columns: 22px minmax(92px, .7fr) minmax(0, 1.3fr); align-items: center; gap: 6px; padding: 0 10px; border: 0; border-bottom: 1px solid var(--app-border-subtle); background: transparent; color: var(--app-text-secondary); text-align: start; cursor: pointer; }
.timeline-row:hover:not(:disabled) { background: var(--app-bg-hover); }
.timeline-row.selected { background: var(--app-bg-active); box-shadow: inset 2px 0 var(--app-color-primary); }
.timeline-row.kind-marker { color: var(--app-color-warning); }
.timeline-row.kind-drop { color: var(--app-color-danger); }
.timeline-row strong { overflow: hidden; color: inherit; font-size: var(--app-font-xs); font-weight: 500; text-overflow: ellipsis; white-space: nowrap; }
.timeline-row > span:last-child { overflow: hidden; font-size: var(--app-font-xs); text-overflow: ellipsis; white-space: nowrap; }
.timeline-glyph { display: grid; place-items: center; }
.viewer-empty { grid-row: 1 / -1; }
.viewer-empty strong { color: var(--app-text-primary); font-size: var(--app-font-md); }
.viewer-empty p { max-width: 440px; margin: 0; line-height: 1.6; }
.inspector-scroll { min-height: 0; overflow: auto; }
.inspector-section { padding: var(--app-form-section-padding) 0; border-bottom: 1px solid var(--app-border-subtle); }
.inspector-section h2 { margin: 0 0 var(--app-form-heading-field-gap); color: var(--app-text-primary); font-size: var(--app-font-sm); font-weight: 600; }
.metadata-list { margin: 0; }
.metadata-list > div { min-height: var(--app-control-compact); display: grid; grid-template-columns: 76px minmax(0, 1fr); align-items: center; gap: 8px; border-bottom: 1px solid var(--app-border-subtle); }
.metadata-list dt { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.metadata-list dd { min-width: 0; margin: 0; overflow: hidden; color: var(--app-text-primary); font-size: var(--app-font-xs); text-overflow: ellipsis; white-space: nowrap; }
.metadata-list.compact { margin-top: 8px; }
.section-empty { margin: 0; color: var(--app-text-placeholder); font-size: var(--app-font-xs); line-height: 1.5; }
.section-help { margin-top: 9px; }
.technical-frame-details { margin-top: 6px; }
.technical-frame-details > summary { min-height: var(--app-control-compact); display: flex; align-items: center; color: var(--app-text-secondary); font-size: var(--app-font-xs); cursor: pointer; }
.technical-frame-details > summary:hover { color: var(--app-text-primary); }
.technical-frame-details .metadata-list { margin-top: 0; }
.verification-result { display: flex; align-items: center; gap: 8px; margin: 10px; padding: 9px 10px; border: 1px solid var(--app-color-success); border-radius: var(--app-radius-sm); color: var(--app-color-success); }
.verification-result.failed { border-color: var(--app-color-danger); color: var(--app-color-danger); }
.verification-result div { display: flex; flex-direction: column; }
.verification-result strong { font-size: var(--app-font-xs); }
.verification-result span { color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.compare-inputs { display: grid; grid-template-columns: 1fr 1fr; gap: 7px; margin-bottom: 8px; }
.compare-inputs label { min-width: 0; display: grid; grid-template-columns: 34px minmax(0, 1fr); align-items: center; gap: 7px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.difference-preview { width: 100%; max-height: 148px; margin-top: 8px; object-fit: contain; background: var(--app-bg-input); }
.analysis-list, .privacy-categories { display: flex; flex-direction: column; gap: 2px; margin-top: 9px; }
.analysis-list label, .privacy-categories label, .choice-row { display: flex; align-items: flex-start; gap: 7px; padding: 6px 5px; border-radius: var(--app-radius-sm); cursor: pointer; }
.analysis-list label:hover, .privacy-categories label:hover, .choice-row:hover { background: var(--app-bg-hover); }
.analysis-list input, .privacy-categories input, .choice-row input { flex: none; margin: 3px 0 0; accent-color: var(--app-color-primary); }
.analysis-list span, .privacy-categories span, .choice-row span { min-width: 0; display: flex; flex-direction: column; }
.analysis-list strong, .privacy-categories strong, .choice-row strong { color: var(--app-text-primary); font-size: var(--app-font-xs); font-weight: 500; }
.analysis-list small, .privacy-categories small, .choice-row small { color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.45; }
.inline-actions { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.analysis-result { margin: 8px 0 0; color: var(--app-color-success); font-size: var(--app-font-xs); overflow-wrap: anywhere; }
.report-history { margin-top: 9px; color: var(--app-text-secondary); font-size: var(--app-font-xs); }
.report-history summary { cursor: pointer; }
.report-row { display: flex; align-items: center; justify-content: space-between; gap: 6px; padding: 7px 0; border-bottom: 1px solid var(--app-border-subtle); }
.report-row > span { min-width: 0; display: flex; flex-direction: column; }
.report-row strong { color: var(--app-text-primary); font-size: var(--app-font-xs); font-weight: 500; }
.report-row small { overflow: hidden; color: var(--app-text-placeholder); text-overflow: ellipsis; white-space: nowrap; }
.report-row button { width: 26px; height: 26px; display: grid; place-items: center; border: 0; border-radius: var(--app-radius-sm); background: transparent; color: var(--app-text-secondary); cursor: pointer; }
.report-row button:hover { background: var(--app-bg-hover); color: var(--app-color-danger); }
.export-scope { margin: 9px 5px; }
.privacy-warning { display: flex; align-items: flex-start; gap: 6px; margin: 9px 0; color: var(--app-color-warning); font-size: var(--app-font-xs); line-height: 1.45; }
.privacy-warning svg { flex: none; margin-top: 2px; }
.danger-zone { padding-bottom: 24px; }
.danger-outline { min-height: var(--app-control-compact); display: inline-flex; align-items: center; gap: 5px; padding: 0 9px; border: 1px solid var(--app-color-danger); border-radius: var(--app-radius-sm); background: transparent; color: var(--app-color-danger); cursor: pointer; }
.delete-confirm { display: flex; flex-direction: column; gap: 7px; padding: 9px; border: 1px solid var(--app-color-danger); border-radius: var(--app-radius-sm); }
.delete-confirm strong { color: var(--app-text-primary); font-size: var(--app-font-sm); }
.delete-confirm > span { color: var(--app-text-secondary); font-size: var(--app-font-xs); line-height: 1.45; }
.delete-confirm > div { display: flex; justify-content: flex-end; gap: 6px; }
.delete-confirm button { height: var(--app-control-compact); padding: 0 8px; border: 1px solid var(--app-border-default); border-radius: var(--app-radius-sm); background: var(--app-bg-raised); color: var(--app-text-regular); cursor: pointer; }
.delete-confirm .danger-solid { border-color: var(--app-color-danger); background: var(--app-color-danger); color: white; }
.workspace-error { display: flex; align-items: flex-start; gap: 6px; padding: 10px 14px 18px; }
.workspace-error svg { flex: none; margin-top: 2px; }
.spin { animation: replay-spin .9s linear infinite; }
@keyframes replay-spin { to { transform: rotate(360deg); } }
@media (max-width: 1120px) { .replay-workspace { position: relative; grid-template-columns: minmax(220px, 250px) minmax(390px, 1fr); } .replay-inspector { position: absolute; z-index: 40; inset: 0 0 0 auto; width: min(360px, calc(100% - 52px)); display: none; box-shadow: var(--app-shadow-lg); } .replay-inspector.is-open { display: grid; } .inspector-close { display: grid !important; } .inspector-toggle { display: inline-flex !important; } }
@media (max-width: 820px) { .replay-workspace { grid-template-columns: minmax(200px, 232px) minmax(360px, 1fr); } .viewer-actions button { width: 28px; padding: 0; font-size: 0; } .timeline-section > header span { display: none; } }
@media (max-width: 700px) {
    .replay-workspace { position: relative; grid-template-columns: minmax(0, 1fr); }
    .replay-sessions {
        position: absolute;
        z-index: 62;
        inset: 0 auto 0 0;
        width: min(320px, calc(100% - 44px));
        display: none;
        border-inline-end-color: var(--app-overlay-border);
        box-shadow: var(--app-shadow-lg);
    }
    .replay-sessions.is-open { display: grid; }
    .replay-scrim { position: absolute; z-index: 55; inset: 0; display: block !important; background: rgba(4, 4, 3, .62); }
    .sessions-close { display: grid !important; }
    .sessions-toggle { position: absolute; z-index: 35; inset: 7px auto auto 7px; display: grid !important; background: var(--app-bg-chrome); }
    .replay-viewer { grid-column: 1; }
    .viewer-header { padding-inline-start: 45px; }
    .replay-inspector { z-index: 62; }
}
@media (max-width: 420px) { .compare-inputs { grid-template-columns: 1fr; } }
@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
@media (min-width: 701px) { .replay-workspace { grid-template-columns: var(--workspace-sidebar-width, 260px) minmax(420px, 1fr) minmax(300px, 360px); } }
@media (min-width: 701px) { .replay-workspace.detail-panel-collapsed { grid-template-columns: var(--workspace-sidebar-width, 260px) minmax(0, 1fr); } }
@media (min-width: 701px) and (max-width: 1120px) { .replay-workspace { grid-template-columns: var(--workspace-sidebar-width, 260px) minmax(0, 1fr); } }
</style>
