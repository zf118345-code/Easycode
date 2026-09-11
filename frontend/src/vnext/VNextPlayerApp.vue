<template>
    <main :class="['player-app', { 'android-host': androidHost, 'is-embedded': embeddedHost }]">
        <VNextDesktopTitlebar v-if="!embeddedHost" class="titlebar" :managed-close="true" @request-close="requestPlayerClose">
            <img v-if="applicationIconUrl" class="application-icon" :src="applicationIconUrl" alt="" />
            <Braces v-else :size="18" /><strong>{{ playerForm.title }}</strong>
            <template v-if="projectName !== playerForm.title" #meta><span>{{ projectName }}</span></template>
        </VNextDesktopTitlebar>
        <section v-if="loading" class="state">
            <LoaderCircle :size="22" class="spin" /><strong>正在加载 Player</strong>
        </section>
        <section v-else-if="startupError" class="state error">
            <CircleAlert :size="22" /><strong>Player 无法启动</strong>
            <p>{{ startupError }}</p>
        </section>
        <div
            v-else
            :class="['layout', { 'without-nav': playerForm.pages.length <= 1, 'runtime-collapsed': !runtimePanelOpen, 'content-collapsed': !contentPanelOpen }]"
            :style="{ '--runtime-panel-width': `${runtimePanelWidth}px` }"
        >
            <VNextOverflowTabs
                v-if="playerForm.pages.length > 1 && contentPanelOpen"
                v-model="activePageId"
                class="page-tabs"
                :items="playerForm.pages.map((page) => ({ id: page.page_id, label: page.title }))"
                label="配置页面"
            />
            <section v-if="androidHost && runtimeMode" class="mobile-context" aria-label="当前运行方案">
                <label>
                    <span>运行方案</span>
                    <select v-model="selectedProfileId" :disabled="interactionLocked" @change="applySelectedProfile">
                        <option v-for="profile in profiles" :key="profile.profile_id" :value="profile.profile_id">{{ profile.name }}</option>
                    </select>
                </label>
                <button type="button" :disabled="interactionLocked || checkingEnvironment" @click="checkEnvironment">
                    <ShieldCheck :size="15" />{{ environmentCheck?.ready ? '环境已就绪' : checkingEnvironment ? '检查中' : '检查环境' }}
                </button>
                <small>{{ selectedProfile ? '方案已保存' : '先保存方案后再采集字段' }} · {{ statusLabel }}</small>
            </section>
            <section v-show="contentPanelOpen" class="content">
                <form v-if="activePage" class="runtime-form" @submit.prevent="runMain">
                    <label
                        v-for="control in activePage.controls"
                        :key="control.control_id"
                        :class="[
                            `span-${control.layout.span}`,
                            { 'is-inline-field': playerControlUsesInlineLayout(control) },
                        ]"
                        :data-control-id="control.control_id"
                    >
                        <span v-if="control.type !== 'button'"
                            >{{ control.label }}<b v-if="control.required">*</b></span
                        >
                        <VNextPlayerValueControl
                            v-if="control.type !== 'button'"
                            v-model="values[control.control_id]"
                            :control="control"
                            :assets="assets"
                            :platform="runtimePlatform"
                        />
                        <button
                            v-else
                            type="button"
                            class="secondary"
                            :disabled="interactionLocked"
                            @click="runAction(control.control_id)"
                        >
                            <Play :size="14" />{{ control.label }}
                        </button>
                        <div v-if="runtimeMode && terminalActionsFor(control.control_id).length" class="terminal-actions" aria-label="终端字段操作">
                            <button
                                v-if="terminalActionsFor(control.control_id)[0]"
                                type="button"
                                :disabled="!terminalActionsFor(control.control_id)[0].enabled || captureActive"
                                :title="terminalActionsFor(control.control_id)[0].disabled_reason || terminalActionLabel(terminalActionsFor(control.control_id)[0].action_id)"
                                @click="beginTerminalAction(terminalActionsFor(control.control_id)[0])"
                            >
                                <component :is="terminalActionIcon(terminalActionsFor(control.control_id)[0].action_id)" :size="13" />{{ terminalActionLabel(terminalActionsFor(control.control_id)[0].action_id) }}
                            </button>
                            <details v-if="terminalActionsFor(control.control_id).length > 1">
                                <summary>其他录入方式</summary>
                                <button
                                    v-for="action in terminalActionsFor(control.control_id).slice(1)"
                                    :key="action.action_id"
                                    type="button"
                                    :disabled="!action.enabled || captureActive"
                                    :title="action.disabled_reason || terminalActionLabel(action.action_id)"
                                    @click="beginTerminalAction(action)"
                                ><component :is="terminalActionIcon(action.action_id)" :size="13" />{{ terminalActionLabel(action.action_id) }}</button>
                            </details>
                            <button
                                v-if="selectedProfile?.image_overrides?.[control.control_id]"
                                type="button"
                                :disabled="captureActive || isActive"
                                title="恢复开发者发布的默认图片"
                                @click="restoreProfileImage(control.control_id)"
                            ><RotateCcw :size="13" />恢复默认</button>
                            <span v-if="activeCapture?.destination.control_id === control.control_id" class="capture-progress" role="status">
                                <button v-if="activeCapture.destination.action_id === 'choose-resource' && activeCapture.state === 'awaiting_file'" type="button" @click="chooseCaptureFile"><FolderOpen :size="13" />选择图片文件</button>
                                <span v-else-if="activeCapture.state === 'awaiting_confirmation'" class="capture-candidate">
                                    <component :is="activeCapture.candidate?.kind === 'directory' ? Folder : FileInput" :size="13" />
                                    <span>{{ activeCapture.candidate?.display_name || '已取得候选内容' }}</span>
                                    <small>正在安全保存…</small>
                                </span>
                                <span v-else-if="activeCapture.destination.action_id === 'capture-control'" class="capture-instruction">
                                    {{ androidHost
                                        ? '切到目标应用，在悬浮条选择控件；冻结后点击控件，可逐级切换父级'
                                        : '将鼠标停在目标控件上，看到高亮后按 Ctrl+Shift+Enter' }}
                                </span>
                                <span v-else>{{ androidHost ? '请在悬浮工具中完成采集；确认成功前会保留原值' : '已打开采集画面，请在画面中完成选择' }}</span>
                                <button type="button" @click="cancelActiveCapture">取消</button>
                            </span>
                            <small v-if="terminalActionsFor(control.control_id).some((action) => !action.enabled)" class="terminal-action-reason">{{ terminalActionsFor(control.control_id).find((action) => !action.enabled)?.disabled_reason }}</small>
                        </div>
                        <small v-if="control.help && control.type !== 'text' && control.type !== 'button'">{{
                            control.help
                        }}</small>
                    </label>
                </form>
                <div v-else class="state"><LayoutTemplate :size="24" /><strong>开发者尚未配置运行页面</strong></div>
            </section>
            <VNextPaneResizer
                v-if="runtimePanelOpen && contentPanelOpen && !androidHost"
                v-model="runtimePanelWidth"
                class="runtime-panel-resizer"
                orientation="vertical"
                :min="280"
                :max="480"
                :default-value="320"
                :reverse="true"
                label="调整运行面板宽度"
                @commit="persistPlayerLayout"
            />
            <VNextIconButton v-if="!runtimePanelOpen && !androidHost" class="runtime-panel-restore" label="展开运行面板" @click="openRuntimePanel"><PanelRightOpen /></VNextIconButton>
            <aside v-show="runtimePanelOpen" class="runtime-panel">
                <header>
                    <strong>运行</strong>
                    <span class="runtime-heading-actions">
                        <span>{{ statusLabel }}</span>
                        <VNextIconButton
                            v-if="!androidHost"
                            :label="contentPanelOpen ? '收起配置内容' : '展开配置内容'"
                            @click="toggleContentPanel"
                        ><PanelLeftClose v-if="contentPanelOpen" /><PanelLeftOpen v-else /></VNextIconButton>
                        <VNextIconButton v-if="!androidHost" label="收起运行面板" @click="closeRuntimePanel"><PanelRightClose /></VNextIconButton>
                    </span>
                </header>
                <div v-if="operationError" class="runtime-error" role="alert">
                    <CircleAlert :size="15" />
                    <span>{{ operationError }}</span>
                    <button type="button" aria-label="关闭错误提示" title="关闭错误提示" @click="operationError = ''">
                        <X :size="14" />
                    </button>
                </div>
                <VNextPlayerUpdates
                    v-if="playerUpdates?.enabled"
                    :initial="playerUpdates"
                    :runtime-active="isActive"
                    :uncommitted-draft="hasUncommittedDraft"
                    @content-applied="reloadAppliedContent"
                />
                <section v-if="embeddedHost" class="support-actions" aria-label="诊断与反馈">
                    <VNextButton size="compact" @click="requestConsoleSupport('copy-summary')"><template #icon><Copy /></template>复制摘要</VNextButton>
                    <VNextButton size="compact" @click="requestConsoleSupport('download-diagnostics')"><template #icon><Download /></template>诊断包</VNextButton>
                </section>
                <section v-if="runtimeMode" class="runtime-tools" aria-label="运行准备">
                    <div class="tool-heading">
                        <strong>运行准备</strong>
                        <button v-if="!androidHost" type="button" :disabled="interactionLocked || checkingEnvironment" @click="checkEnvironment">
                            <ShieldCheck :size="13" />{{ checkingEnvironment ? '检查中' : '环境检查' }}
                        </button>
                    </div>
                    <div v-if="environmentCheck" :class="['environment-report', { ready: environmentCheck.ready }]" role="status">
                        <span>{{ environmentCheck.ready ? '环境可运行' : '环境未就绪' }}<small v-if="environmentCheck.duration_ms">{{ environmentCheck.duration_ms }}ms</small></span>
                        <p v-for="check in environmentCheck.checks" :key="check.id" :class="check.status">{{ check.message }}</p>
                    </div>
                    <label v-if="!androidHost">配置方案
                        <select v-model="selectedProfileId" :disabled="interactionLocked" @change="applySelectedProfile">
                            <option value="">当前配置（终端采集关闭）</option>
                            <option v-for="profile in profiles" :key="profile.profile_id" :value="profile.profile_id">{{ profile.name }}</option>
                        </select>
                    </label>
                    <div class="profile-actions">
                        <input v-model.trim="profileName" :disabled="interactionLocked" maxlength="80" placeholder="方案名称" @keydown.enter.prevent="saveProfile" />
                        <button type="button" title="保存当前配置" :disabled="interactionLocked || !profileName || savingProfile" @click="saveProfile"><Save :size="13" /></button>
                        <button type="button" title="删除所选方案" :disabled="interactionLocked || !selectedProfileId" @click="deleteProfile"><Trash2 :size="13" /></button>
                    </div>
                    <p v-if="terminalActionsBlockedReason" class="profile-notice" role="status">
                        <CircleAlert :size="13" />
                        <span>{{ terminalActionsBlockedReason }}</span>
                    </p>
                    <details v-if="recordingFeatureEnabled" class="recording-settings">
                        <summary>
                            <span><Film :size="13" />运行录制</span>
                            <em>{{ recordingDraft.enabled ? '已启用' : '关闭' }}</em>
                        </summary>
                        <label class="recording-toggle">
                            <input
                                v-model="recordingDraft.enabled"
                                type="checkbox"
                                :disabled="interactionLocked || !recordingSupportedTarget"
                            />
                            <span>运行时保存原始帧，用于复盘与无副作用分析</span>
                        </label>
                        <p v-if="!recordingSupportedTarget" class="recording-note">选择 Windows、ADB 或 Android 本机目标后才能启用。</p>
                        <p v-else-if="recordingDraft.enabled && !selectedProfile" class="recording-note">保存为配置方案后，本次确认才会与方案 revision 绑定；“当前配置”运行不会录制。</p>
                        <p v-else-if="recordingDraft.enabled && !recordingConsentCurrent" class="recording-note warning">方案或目标已变化。请重新保存方案，确认这一 revision 后才会录制。</p>
                        <div v-if="recordingDraft.enabled" class="recording-fields">
                            <label>策略
                                <select v-model="recordingDraft.strategy" :disabled="interactionLocked">
                                    <option value="changed_frames">变化帧（推荐）</option>
                                    <option value="all_frames">全部帧</option>
                                    <option value="diagnostic">诊断片段</option>
                                </select>
                            </label>
                            <label>帧率
                                <input v-model.number="recordingDraft.target_fps" type="number" min="0.2" max="60" step="0.2" :disabled="interactionLocked" />
                            </label>
                            <label>最长分钟
                                <input v-model.number="recordingMaxMinutes" type="number" min="1" max="10080" step="1" :disabled="interactionLocked" />
                            </label>
                            <label>空间上限 MB
                                <input v-model.number="recordingMaxMegabytes" type="number" min="1" max="953674" step="64" :disabled="interactionLocked" />
                            </label>
                        </div>
                        <small>录制内容仅保存在本机，不自动上传。达到时长、空间或磁盘保护阈值时会安全停止录制，任务继续运行。</small>
                        <div class="recording-history-heading">
                            <span>本机记录</span>
                            <button type="button" :disabled="recordingHistoryBusy" @click="refreshRecordingHistory"><RotateCw :size="11" />刷新</button>
                        </div>
                        <p v-if="!recordingSessions.length" class="recording-empty">暂无录制记录</p>
                        <button
                            v-for="session in recordingSessions.slice(0, 12)"
                            :key="session.session_id"
                            type="button"
                            class="recording-session-row"
                            :disabled="recordingHistoryBusy"
                            @click="openRecordingSession(session.session_id)"
                        >
                            <span><strong>{{ formatRecordingTime(session.started_at) }}</strong><small>{{ session.target_title || '运行目标' }} · {{ session.frame_count || 0 }} 帧</small></span>
                            <em>{{ recordingStatusLabel(session.status, session.terminal_reason) }}</em>
                        </button>
                    </details>
                    <VNextPlayerSchedules
                        v-if="androidHost"
                        :profiles="profiles"
                        :disabled="interactionLocked"
                        @feedback="presentHostFeedback"
                    />
                    <VNextPlayerDevices v-if="androidHost" @feedback="presentHostFeedback" />
                </section>
                <label v-if="targets.length > 1"
                    >运行目标<select v-model="targetId" :disabled="interactionLocked" @change="environmentCheck = null">
                        <option :value="null">无目标</option>
                        <option v-for="target in targets" :key="target.target_id" :value="target.target_id">
                            {{ target.name }}
                        </option>
                    </select></label
                >
                <div class="actions">
                    <button v-if="!isActive" type="button" class="primary" :disabled="updateBlocksNewTask" :title="updateBlocksNewTask ? '签名最低版本策略要求先更新' : '运行主程序'" @click="runMain">
                        <Play :size="14" />运行主程序</button
                    ><button v-if="execution?.status === 'running'" type="button" class="secondary" @click="pause"><Pause :size="13" />暂停</button
                    ><button v-if="execution?.status === 'paused'" type="button" class="secondary" @click="resume"><Play :size="13" />继续</button
                    ><button v-if="isActive && !serviceDisconnected" type="button" class="danger" @click="stop"><Square :size="13" />停止</button>
                </div>
                <div v-if="recordingFeatureEnabled && playerRecording && (playerRecording.active || playerRecording.status === 'error' || playerRecording.requested_enabled)" class="recording-runtime" role="status">
                    <span><Film :size="13" /><strong>{{ recordingStateLabel(playerRecording) }}</strong></span>
                    <p v-if="playerRecording.active">{{ playerRecording.frame_count || 0 }} 帧 · {{ formatBytes(playerRecording.disk_bytes || 0) }}<template v-if="playerRecording.dropped_frame_count"> · 丢弃 {{ playerRecording.dropped_frame_count }}</template></p>
                    <p v-else>{{ playerRecording.last_error || recordingReasonLabel(playerRecording.reason || playerRecording.terminal_reason || '') }}</p>
                    <button v-if="playerRecording.active && playerRecording.status !== 'stopping'" type="button" @click="stopRecording"><Square :size="12" />只停止录制</button>
                </div>
                <div v-if="execution && !isActive" class="result-actions">
                    <button type="button" @click="retry"><RotateCw :size="13" />重新运行</button>
                    <a v-if="execution.failure_frame_available" :href="`/api/vnext/runs/${execution.execution_id}/failure-frame`" target="_blank"><Image :size="13" />失败截图</a>
                    <a v-if="execution.diagnostic_available" :href="`/api/vnext/runs/${execution.execution_id}/diagnostics`" download><Download :size="13" />诊断包</a>
                </div>
                <header class="log-heading"><span>运行日志</span><span><button type="button" title="复制日志" :disabled="!visibleEvents.length" @click="copyLogs"><Copy :size="13" /></button><button type="button" title="清空当前日志视图" :disabled="!visibleEvents.length" @click="clearLogs"><Eraser :size="13" /></button></span></header>
                <div class="runtime-log" aria-live="polite">
                    <div v-for="event in visibleEvents" :key="event.sequence">
                        <time>{{ event.timestamp.slice(11, 19) }}</time
                        ><span>{{ event.message }}</span>
                    </div>
                    <p v-if="!visibleEvents.length">运行日志会显示在这里。</p>
                </div>
            </aside>
        </div>
        <VNextConfirmDialog
            :open="pendingPlayerClose"
            title="停止任务并退出？"
            message="当前脚本仍在运行。退出将安全停止本次运行与录制，然后完整关闭 Player。"
            confirm-label="停止并退出"
            tone="warning"
            :busy="closingPlayer"
            :dismiss-on-backdrop="false"
            @cancel="cancelPlayerClose"
            @confirm="confirmPlayerClose"
        />
        <VNextConfirmDialog
            :open="Boolean(pendingDangerousRun)"
            title="确认递归删除目录"
            message="此确认只对本次运行和下列授权目录有效，不会保存到配置方案。"
            :confirm-label="confirmingDangerousRun ? '正在启动' : '确认并运行'"
            tone="warning"
            :busy="confirmingDangerousRun"
            :dismiss-on-backdrop="false"
            @cancel="cancelDangerousRun"
            @confirm="confirmDangerousRun"
        >
            <ul class="danger-operation-list">
                <li v-for="operation in pendingDangerousRun?.operations || []" :key="operation.confirmation_id">
                    <strong>{{ operation.display_name }}</strong>
                    <code :title="operation.display_path">{{ operation.display_path }}</code>
                </li>
            </ul>
            <p class="danger-operation-note">目录及全部后代将被永久删除。运行时仍会阻止盘符根、工作区、用户目录和符号链接逃逸。</p>
        </VNextConfirmDialog>
        <div v-if="selectedRecordingSession" class="recording-viewer-backdrop" @click.self="closeRecordingSession">
            <section ref="recordingDialogElement" class="recording-viewer" role="dialog" aria-modal="true" aria-label="录制记录" tabindex="-1" @keydown="trapDialogFocus" @keydown.esc.stop="closeRecordingSession">
                <header>
                    <span><strong>{{ formatRecordingTime(selectedRecordingSession.started_at) }}</strong><small>{{ selectedRecordingSession.frame_total ?? selectedRecordingSession.frames.length }} 帧 · {{ formatBytes(selectedRecordingSession.disk_bytes || 0) }}</small></span>
                    <button type="button" aria-label="关闭录制记录" data-dialog-initial-focus @click="closeRecordingSession"><X :size="16" /></button>
                </header>
                <div class="recording-frame-stage">
                    <LoaderCircle v-if="recordingFrameBusy" :size="22" class="spin" />
                    <img v-else-if="recordingFrameUrl" :src="recordingFrameUrl" alt="录制帧预览" />
                    <p v-else>{{ selectedRecordingSession.frames.length ? '选择一帧查看' : '这次录制没有保存画面' }}</p>
                </div>
                <footer>
                    <button type="button" :disabled="recordingFrameIndex <= 0 || recordingFrameBusy" @click="stepRecordingFrame(-1)"><ChevronLeft :size="14" />上一帧</button>
                    <span v-if="selectedRecordingSession.frames.length">{{ recordingFrameIndex + 1 }} / {{ selectedRecordingSession.frames.length }}</span>
                    <button type="button" :disabled="recordingFrameIndex >= selectedRecordingSession.frames.length - 1 || recordingFrameBusy" @click="stepRecordingFrame(1)">下一帧<ChevronRight :size="14" /></button>
                    <button type="button" :disabled="recordingHistoryBusy" @click="exportRecordingSession"><Download :size="13" />导出</button>
                    <button type="button" class="danger-text" :disabled="recordingHistoryBusy" @click="pendingRecordingDelete = selectedRecordingSession.session_id"><Trash2 :size="13" />删除记录</button>
                </footer>
            </section>
        </div>
        <VNextConfirmDialog
            :open="Boolean(pendingRecordingDelete)"
            title="删除录制记录"
            message="将永久删除这次录制保存的全部原始帧和诊断索引。"
            confirm-label="确认删除"
            tone="warning"
            :busy="recordingHistoryBusy"
            @cancel="pendingRecordingDelete = ''"
            @confirm="deleteRecordingSession"
        />
        <div
            v-if="feedback.message"
            :class="['player-feedback', feedback.tone]"
            :role="feedback.tone === 'error' ? 'alert' : 'status'"
            :aria-live="feedback.tone === 'error' ? 'assertive' : 'polite'"
        >
            <CircleAlert v-if="feedback.tone === 'error'" :size="16" />
            <ShieldCheck v-else :size="16" />
            <span>{{ feedback.message }}</span>
            <button type="button" aria-label="关闭提示" @click="dismissFeedback"><X :size="15" /></button>
        </div>
    </main>
</template>

<script setup lang="ts">
import { computed, markRaw, nextTick, onBeforeUnmount, onMounted, reactive, ref, toRaw, watch } from 'vue'
import { AppWindow, Braces, ChevronLeft, ChevronRight, CircleAlert, Copy, Crosshair, Download, Eraser, FileInput, Film, Folder, FolderOpen, Image, ImagePlus, LayoutTemplate, LoaderCircle, MousePointer2, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Pause, Pipette, Play, RotateCcw, RotateCw, Route, Save, ScanLine, ShieldCheck, Square, Trash2, X } from 'lucide-vue-next'
import { mergeRuntimeSession, vnextApi } from './playerApi'
import type { PlayerRuntimeRunPayload } from './playerApi'
import VNextPlayerValueControl from './components/VNextPlayerValueControl.vue'
import VNextPlayerUpdates from './components/VNextPlayerUpdates.vue'
import VNextPlayerSchedules from './components/VNextPlayerSchedules.vue'
import VNextPlayerDevices from './components/VNextPlayerDevices.vue'
import VNextConfirmDialog from './components/VNextConfirmDialog.vue'
import VNextDesktopTitlebar from './components/ui/VNextDesktopTitlebar.vue'
import VNextButton from './components/ui/VNextButton.vue'
import VNextIconButton from './components/ui/VNextIconButton.vue'
import VNextOverflowTabs from './components/ui/VNextOverflowTabs.vue'
import VNextPaneResizer from './components/VNextPaneResizer.vue'
import { sendNativeWindowCommand } from './nativeWindowBridge'
import { trapDialogFocus, useDialogFocusReturn } from './dialogFocus'
import type { AssetDefinition, PlatformId, PlayerControlDefinition, PlayerControlDestination, PlayerControlType, PlayerDangerousOperationRequirement, PlayerEnvironmentCheck, PlayerFormDefinition, PlayerProfile, PlayerRecordingSessionDetail, PlayerRecordingSessionSummary, PlayerRecordingSettings, PlayerRecordingStatus, PlayerTerminalActionAvailability, PlayerUpdatesResponse, RuntimeSession, TargetDefinition } from './types'

const loading = ref(true),
    startupError = ref(''),
    operationError = ref(''),
    activePageId = ref(''),
    targetId = ref<string | null>(null)
const pendingPlayerClose = ref(false)
const closingPlayer = ref(false)
const serviceDisconnected = ref(false)
const androidHost = Boolean(window.EasyCodeAndroid)
const embeddedHost = new URLSearchParams(window.location.search).get('embedded') === '1'
const consoleParentOrigin = (() => {
    if (!embeddedHost || !document.referrer) return ''
    try { return new URL(document.referrer).origin } catch { return '' }
})()
const runtimePanelWidth = ref(readLayoutNumber('easycode.player.runtimePanelWidth', 320, 280, 480))
const runtimePanelOpen = ref(readLayoutBoolean('easycode.player.runtimePanelOpen', true))
const contentPanelOpen = ref(readLayoutBoolean('easycode.player.contentPanelOpen', true))
const values = reactive<Record<string, unknown>>({}),
    execution = ref<RuntimeSession | null>(null)
const baselineValues = ref<Record<string, unknown>>({}),
    defaultTargetId = ref<string | null>(null)
const runtimeMode = ref(false),
    projectName = ref('EasyCode Player')
const environmentCheck = ref<PlayerEnvironmentCheck | null>(null),
    checkingEnvironment = ref(false),
    profiles = ref<PlayerProfile[]>([]),
    selectedProfileId = ref(''),
    profileName = ref(''),
    savingProfile = ref(false),
    clearedThrough = ref(0)
const playerForm = ref<PlayerFormDefinition>({ schema_version: 3, title: '脚本运行器', features: { recording: false }, pages: [] })
const targets = ref<TargetDefinition[]>([]),
    assets = ref<AssetDefinition[]>([])
const productId = ref(''),
    releaseId = ref(''),
    terminalActions = ref<PlayerTerminalActionAvailability[]>([]),
    terminalActionsBlockedReason = ref('')
const activeCapture = ref<{
    capture_id: string
    destination: PlayerControlDestination
    state: string
    candidate?: { candidate_id: string; kind: 'file' | 'directory'; display_name: string; access: string[] }
} | null>(null)
const pendingCaptureResult = ref<Record<string, unknown> | null>(null)
const recordingDraft = reactive<PlayerRecordingSettings>(defaultRecordingSettings())
const playerRecording = ref<PlayerRecordingStatus | null>(null)
const recordingSessions = ref<PlayerRecordingSessionSummary[]>([])
const selectedRecordingSession = ref<PlayerRecordingSessionDetail | null>(null)
const recordingDialogElement = ref<HTMLElement | null>(null)
const recordingFrameIndex = ref(0)
const recordingFrameUrl = ref('')
const recordingHistoryBusy = ref(false)
const recordingFrameBusy = ref(false)
const pendingRecordingDelete = ref('')
const playerUpdates = ref<PlayerUpdatesResponse | null>(null)
const pendingDangerousRun = ref<{
    payload: PlayerRuntimeRunPayload
    operations: PlayerDangerousOperationRequirement[]
} | null>(null)
const confirmingDangerousRun = ref(false)
useDialogFocusReturn(() => Boolean(selectedRecordingSession.value), recordingDialogElement)
const feedback = reactive<{ message: string; tone: 'success' | 'error' }>({ message: '', tone: 'success' })
let followToken = 0
let disposed = false
let feedbackTimer: ReturnType<typeof setTimeout> | null = null
let lastActionControlId = ''
let captureEventSource: EventSource | null = null
let captureCompleting = false
let actionRefreshToken = 0
const activePage = computed(
    () =>
        playerForm.value.pages.find((item) => item.page_id === activePageId.value) || playerForm.value.pages[0] || null
)
const applicationIconUrl = computed(() => {
    const assetId = String(playerForm.value.icon_asset_id || '')
    return assetId && assets.value.some((asset) => asset.asset_id === assetId)
        ? `/api/vnext/player/runtime/assets/${encodeURIComponent(assetId)}/content`
        : ''
})
const stackedPlayerControlTypes = new Set<PlayerControlType>([
    'button',
    'coordinate',
    'region',
    'gesture-path',
    'json',
    'list',
    'key-value',
    'expression',
])
const playerControlUsesInlineLayout = (control: PlayerControlDefinition) =>
    !stackedPlayerControlTypes.has(control.type)
const isActive = computed(() => ['queued', 'running', 'paused'].includes(execution.value?.status || ''))
const captureActive = computed(() => Boolean(activeCapture.value))
const interactionLocked = computed(() => isActive.value || captureActive.value)
const profileMetadataDirty = computed(() => {
    const profile = selectedProfile.value
    if (!profile) {
        return Boolean(profileName.value)
            || targetId.value !== defaultTargetId.value
            || JSON.stringify(values) !== JSON.stringify(baselineValues.value)
    }
    return profileName.value !== profile.name
        || targetId.value !== profile.target_id
        || JSON.stringify(values) !== JSON.stringify(baselineValues.value)
})
const hasUncommittedDraft = computed(() => profileMetadataDirty.value)
const updateBlocksNewTask = computed(() => Object.values(playerUpdates.value?.domains || {}).some((item) => item?.can_start_task === false))
const selectedProfile = computed(() => profiles.value.find((item) => item.profile_id === selectedProfileId.value) || null)
const recordingFeatureEnabled = computed(() => playerForm.value.features?.recording === true)
const selectedTarget = computed(() => targets.value.find((item) => item.target_id === targetId.value) || null)
const recordingSupportedTarget = computed(() => ['windows', 'android_adb', 'android_local'].includes(selectedTarget.value?.type || ''))
const recordingConsentCurrent = computed(() => Boolean(
    selectedProfile.value
    && selectedProfile.value.target_id === targetId.value
    && selectedProfile.value.recording?.confirmed_profile_revision === selectedProfile.value.revision,
))
const recordingMaxMinutes = computed({
    get: () => Math.max(1, Math.round(recordingDraft.max_duration_ms / 60_000)),
    set: (value: number) => { recordingDraft.max_duration_ms = Math.max(1, Number(value) || 1) * 60_000 },
})
const recordingMaxMegabytes = computed({
    get: () => Math.max(1, Math.round(recordingDraft.max_session_bytes / 1_048_576)),
    set: (value: number) => { recordingDraft.max_session_bytes = Math.max(1, Number(value) || 1) * 1_048_576 },
})
const visibleEvents = computed(() => (execution.value?.events || []).filter((event) => event.sequence > clearedThrough.value))
const runtimePlatform = computed<PlatformId>(() => {
    const target = targets.value.find((item) => item.target_id === targetId.value)
    return target?.type === 'android_adb'
        ? 'android_adb'
        : target?.type === 'android_local'
          ? 'android_local'
          : 'windows'
})
const statusLabel = computed(() => {
    const labels: Record<string, string> = {
        queued: '等待',
        running: '运行中',
        paused: '已暂停',
        completed: '已完成',
        failed: '失败',
        cancelled: '已停止',
    }
    return labels[execution.value?.status || ''] || '就绪'
})
function readLayoutNumber(key: string, fallback: number, min: number, max: number) {
    try {
        const value = Number(localStorage.getItem(key))
        return Number.isFinite(value) ? Math.max(min, Math.min(max, value)) : fallback
    } catch { return fallback }
}
function readLayoutBoolean(key: string, fallback: boolean) {
    try {
        const value = localStorage.getItem(key)
        return value === null ? fallback : value === 'true'
    } catch { return fallback }
}
function persistPlayerLayout() {
    try {
        localStorage.setItem('easycode.player.runtimePanelWidth', String(runtimePanelWidth.value))
        localStorage.setItem('easycode.player.runtimePanelOpen', String(runtimePanelOpen.value))
        localStorage.setItem('easycode.player.contentPanelOpen', String(contentPanelOpen.value))
    } catch { /* View state persistence is best-effort. */ }
}
function openRuntimePanel() {
    runtimePanelOpen.value = true
    persistPlayerLayout()
}
function closeRuntimePanel() {
    contentPanelOpen.value = true
    runtimePanelOpen.value = false
    persistPlayerLayout()
}
function toggleContentPanel() {
    contentPanelOpen.value = !contentPanelOpen.value
    if (!contentPanelOpen.value) runtimePanelOpen.value = true
    persistPlayerLayout()
}
function requestConsoleSupport(action: 'copy-summary' | 'download-diagnostics') {
    if (!consoleParentOrigin || window.parent === window) return
    window.parent.postMessage({ event: 'easycode-player-console-support', version: 1, action }, consoleParentOrigin)
}
function handleConsoleCommand(event: MessageEvent) {
    if (!embeddedHost || event.source !== window.parent || event.origin !== consoleParentOrigin) return
    const message = event.data as { event?: string; version?: number; command?: string } | null
    if (!message || message.event !== 'easycode-player-console-command' || message.version !== 1) return
    if (message.command === 'run' && !isActive.value) void runMain()
}
function defaultRecordingSettings(): PlayerRecordingSettings {
    return {
        enabled: false,
        strategy: 'changed_frames',
        target_fps: 15,
        max_duration_ms: 1_800_000,
        max_session_bytes: 2_147_483_648,
        min_free_bytes: 536_870_912,
        confirmed_profile_revision: null,
    }
}
function loadRecordingDraft(settings?: PlayerRecordingSettings) {
    Object.assign(
        recordingDraft,
        defaultRecordingSettings(),
        settings ? structuredClone(toRaw(settings)) : {},
    )
}
function formatBytes(value: number) {
    if (value < 1_048_576) return `${Math.max(0, Math.round(value / 1024))} KB`
    return `${(value / 1_048_576).toFixed(value < 10_485_760 ? 1 : 0)} MB`
}
function recordingReasonLabel(reason: string) {
    return ({
        completed: '任务结束，录制记录已经完整保存',
        task_failed: '任务执行失败，录制记录已经完整保存',
        user_stopped: '录制已由用户单独停止',
        user_cancelled: '任务停止，录制记录已经保存',
        disk_protection: '剩余空间触发保护，录制已停止',
        permission_revoked: '屏幕捕获权限已失效',
        quota_reached: '本次录制达到容量上限',
        duration_reached: '本次录制达到时长上限',
        profile_revision_not_confirmed: '方案 revision 尚未确认',
        target_override_not_confirmed: '临时目标未写入并确认到方案',
        recording_requires_saved_profile: '录制只对已保存方案开放',
        profile_disabled: '当前方案没有启用录制',
        feature_not_published: '开发者没有为当前 Player 发布运行录制能力',
        target_missing: '当前方案没有可截图目标',
        driver_failed: '录制宿主启动失败',
    } as Record<string, string>)[reason] || reason || '录制没有启动'
}
function recordingStateLabel(recording: PlayerRecordingStatus) {
    if (recording.status === 'stopping') return '正在结束录制'
    if (recording.status === 'completed') return '录制已完成'
    if (recording.status === 'stopped') return '录制已停止'
    if (recording.status === 'error') return '录制异常'
    if (recording.active) return '正在录制'
    return '录制未启动'
}
function recordingStatusLabel(status = '', reason = '') {
    if (reason === 'process_interrupted') return '意外中断'
    if (status === 'completed') return '已完成'
    if (status === 'stopped') return '已停止'
    if (status === 'error') return '异常'
    if (status === 'recording' || status === 'starting') return '录制中'
    return status || '记录'
}
function formatRecordingTime(value = '') {
    if (!value) return '时间未知'
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
async function refreshRecordingHistory() {
    if (!runtimeMode.value || !recordingFeatureEnabled.value || recordingHistoryBusy.value) return
    recordingHistoryBusy.value = true
    try {
        recordingSessions.value = (await vnextApi.playerRuntimeRecordingSessions()).sessions
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '录制记录加载失败'
    } finally { recordingHistoryBusy.value = false }
}
async function openRecordingSession(sessionId: string) {
    recordingHistoryBusy.value = true
    operationError.value = ''
    try {
        const detail = await vnextApi.playerRuntimeRecordingSession(sessionId)
        selectedRecordingSession.value = detail.session ? { ...detail.session, ...detail } : detail
        recordingFrameIndex.value = 0
        await loadRecordingFrame()
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '录制记录无法打开'
    } finally { recordingHistoryBusy.value = false }
}
async function loadRecordingFrame() {
    const session = selectedRecordingSession.value
    const frame = session?.frames[recordingFrameIndex.value]
    recordingFrameUrl.value = ''
    if (!session || !frame) return
    recordingFrameBusy.value = true
    try {
        const result = await vnextApi.playerRuntimeRecordingFrame(session.session_id, frame.sequence)
        recordingFrameUrl.value = `data:${result.mime_type};base64,${result.data_base64}`
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '录制帧无法读取'
    } finally { recordingFrameBusy.value = false }
}
async function stepRecordingFrame(offset: number) {
    const count = selectedRecordingSession.value?.frames.length || 0
    recordingFrameIndex.value = Math.max(0, Math.min(count - 1, recordingFrameIndex.value + offset))
    await loadRecordingFrame()
}
function closeRecordingSession() {
    selectedRecordingSession.value = null
    recordingFrameUrl.value = ''
}
async function deleteRecordingSession() {
    const sessionId = pendingRecordingDelete.value
    if (!sessionId) return
    recordingHistoryBusy.value = true
    try {
        await vnextApi.deletePlayerRuntimeRecordingSession(sessionId)
        recordingSessions.value = recordingSessions.value.filter((item) => item.session_id !== sessionId)
        pendingRecordingDelete.value = ''
        closeRecordingSession()
        showFeedback('录制记录已删除', 'success')
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '录制记录删除失败'
    } finally { recordingHistoryBusy.value = false }
}
async function exportRecordingSession() {
    const session = selectedRecordingSession.value
    if (!session || recordingHistoryBusy.value) return
    recordingHistoryBusy.value = true
    operationError.value = ''
    try {
        const result = await vnextApi.createPlayerRuntimeRecordingExport(session.session_id)
        if (androidHost) {
            showFeedback('正在准备“画面与报告”压缩包，随后请选择保存位置', 'success')
            return
        }
        if (!result.export_id) throw new Error('录制导出没有生成文件编号')
        const blob = await vnextApi.playerRuntimeRecordingExportBlob(session.session_id, result.export_id)
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement('a')
        anchor.href = url
        anchor.download = `${session.session_id}-画面与报告.zip`
        anchor.click()
        setTimeout(() => URL.revokeObjectURL(url), 0)
        showFeedback('录制导出已生成', 'success')
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '录制导出失败'
    } finally { recordingHistoryBusy.value = false }
}
const terminalIcons: Record<string, unknown> = {
    'pick-point': markRaw(Crosshair),
    'pick-region': markRaw(ScanLine),
    'pick-color': markRaw(Pipette),
    'capture-image': markRaw(ImagePlus),
    'choose-resource': markRaw(FolderOpen),
    'capture-control': markRaw(MousePointer2),
    'capture-window': markRaw(AppWindow),
    'capture-path': markRaw(Route),
    'choose-file-read': markRaw(FileInput),
    'choose-file-save': markRaw(Save),
    'choose-directory': markRaw(Folder),
}
function terminalActionIcon(actionId: string) { return terminalIcons[actionId] || Crosshair }
function terminalActionLabel(actionId: string) { return ({ 'pick-point': '拾取坐标', 'pick-region': '框选区域', 'pick-color': '从目标画面取色', 'capture-image': '截取图片', 'choose-resource': '选择图片', 'capture-control': '捕获控件', 'capture-window': '捕获目标窗口', 'capture-path': '绘制路径', 'choose-file-read': '选择读取文件', 'choose-file-save': '选择保存位置', 'choose-directory': '选择文件夹' } as Record<string, string>)[actionId] || actionId }
function terminalActionsFor(controlId: string) { return terminalActions.value.filter((item) => item.control_id === controlId) }
async function refreshTerminalActions() {
    if (!runtimeMode.value) return
    const token = ++actionRefreshToken
    try {
        const response = await vnextApi.playerRuntimeActions(
            selectedProfileId.value,
            selectedProfile.value?.revision || null,
            targetId.value,
        )
        if (token === actionRefreshToken && !disposed) {
            terminalActions.value = response.actions
            terminalActionsBlockedReason.value = response.blocked_reason || ''
        }
    } catch (value) {
        if (token === actionRefreshToken && !disposed) {
            terminalActions.value = []
            const message = value instanceof Error ? value.message : '无法读取终端字段操作'
            terminalActionsBlockedReason.value = message
            operationError.value = message
        }
    }
}
function resetValues(overrides: Record<string, unknown> = {}) {
    Object.keys(values).forEach((key) => delete values[key])
    playerForm.value.pages.forEach((page) =>
        page.controls.forEach((control) => (values[control.control_id] = control.default)),
    )
    Object.entries(overrides).forEach(([key, value]) => (values[key] = value))
}
function rememberValueBaseline() {
    baselineValues.value = structuredClone(toRaw(values))
}
function runValueOverrides(): Record<string, unknown> {
    return Object.fromEntries(
        Object.entries(values).filter(
            ([controlId, value]) => JSON.stringify(value) !== JSON.stringify(baselineValues.value[controlId]),
        ),
    )
}
async function checkEnvironment() {
    checkingEnvironment.value = true
    operationError.value = ''
    try {
        environmentCheck.value = await vnextApi.playerRuntimePreflight(
            targetId.value,
            selectedProfile.value?.profile_id || null,
            selectedProfile.value?.revision || null,
        )
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '环境检查失败'
    } finally {
        checkingEnvironment.value = false
    }
}
function applySelectedProfile() {
    const profile = profiles.value.find((item) => item.profile_id === selectedProfileId.value)
    if (!profile) {
        rememberSelectedProfile('')
        targetId.value = defaultTargetId.value
        profileName.value = ''
        environmentCheck.value = null
        resetValues()
        rememberValueBaseline()
        loadRecordingDraft()
        return
    }
    rememberSelectedProfile(profile.profile_id)
    targetId.value = profile.target_id
    profileName.value = profile.name
    environmentCheck.value = null
    resetValues(profile.values)
    rememberValueBaseline()
    loadRecordingDraft(profile.recording)
}
async function saveProfile() {
    if (!runtimeMode.value || !profileName.value || savingProfile.value) return
    savingProfile.value = true
    operationError.value = ''
    try {
        const result = await vnextApi.savePlayerRuntimeProfile({
            profile_id: selectedProfileId.value || undefined,
            name: profileName.value,
            target_id: targetId.value,
            values: { ...values },
            expected_revision: selectedProfile.value?.revision,
            ...(recordingFeatureEnabled.value ? { recording: {
                enabled: recordingDraft.enabled,
                strategy: recordingDraft.strategy,
                target_fps: recordingDraft.target_fps,
                max_duration_ms: recordingDraft.max_duration_ms,
                max_session_bytes: recordingDraft.max_session_bytes,
                min_free_bytes: recordingDraft.min_free_bytes,
                confirm_current_revision: recordingDraft.enabled,
            } } : {}),
        })
        profiles.value = [...profiles.value.filter((item) => item.profile_id !== result.profile.profile_id), result.profile]
            .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN'))
        selectedProfileId.value = result.profile.profile_id
        rememberSelectedProfile(result.profile.profile_id)
        resetValues(result.profile.values)
        rememberValueBaseline()
        loadRecordingDraft(result.profile.recording)
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '保存配置方案失败'
    } finally {
        savingProfile.value = false
    }
}
async function deleteProfile() {
    if (!selectedProfileId.value) return
    operationError.value = ''
    try {
        await vnextApi.deletePlayerRuntimeProfile(selectedProfileId.value)
        profiles.value = profiles.value.filter((item) => item.profile_id !== selectedProfileId.value)
        selectedProfileId.value = profiles.value[0]?.profile_id || ''
        applySelectedProfile()
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '删除配置方案失败'
    }
}
function selectedProfileStorageKey() {
    return `easycode.player.profile:${productId.value}:${releaseId.value}`
}
function rememberSelectedProfile(profileId: string) {
    if (!runtimeMode.value || typeof localStorage === 'undefined') return
    try {
        if (profileId) localStorage.setItem(selectedProfileStorageKey(), profileId)
        else localStorage.removeItem(selectedProfileStorageKey())
    } catch { /* A blocked browser storage policy must not block Player use. */ }
}
function selectInitialProfile() {
    let preferred = ''
    try { preferred = localStorage.getItem(selectedProfileStorageKey()) || '' }
    catch { /* Fall back to the first saved scheme. */ }
    const profile = profiles.value.find((item) => item.profile_id === preferred) || profiles.value[0]
    selectedProfileId.value = profile?.profile_id || ''
    applySelectedProfile()
}
async function follow(session: RuntimeSession) {
    const token = ++followToken
    execution.value = session
    playerRecording.value = session.recording || null
    let lastRecordingPoll = 0
    let connectionFailures = 0
    while (!disposed && token === followToken && isActive.value) {
        await new Promise((resolve) => setTimeout(resolve, 250))
        if (disposed || token !== followToken) break
        const current = execution.value
        let next: RuntimeSession
        try {
            next = await vnextApi.runStatus(
                session.execution_id,
                current?.event_cursor || current?.events.at(-1)?.sequence || 0,
            )
            connectionFailures = 0
        } catch (error) {
            const status = Number((error as { status?: unknown } | null)?.status || 0)
            if (![408, 503].includes(status)) throw error
            connectionFailures += 1
            if (connectionFailures < 3) {
                await new Promise((resolve) => setTimeout(resolve, 150 * connectionFailures))
                continue
            }
            serviceDisconnected.value = true
            throw new Error('Player 实例服务连接已中断，本次运行结果未知。请勿重复启动；请在多实例控制台导出最近诊断包后原位重启该实例。')
        }
        if (!disposed && token === followToken) execution.value = mergeRuntimeSession(current, next)
        if (recordingFeatureEnabled.value && Date.now() - lastRecordingPoll >= 1_000 && playerRecording.value?.active) {
            lastRecordingPoll = Date.now()
            playerRecording.value = await vnextApi.playerRuntimeRecordingStatus().catch(() => playerRecording.value)
        }
    }
    if (!disposed && token === followToken && recordingFeatureEnabled.value && playerRecording.value) {
        playerRecording.value = await vnextApi.playerRuntimeRecordingStatus().catch(() => playerRecording.value)
    }
    // A terminal run may have just created or finalized a recording.  Refresh
    // the user-visible history here so it never requires a manual reload to
    // reveal a recording that the same screen just produced.
    if (!disposed && token === followToken && recordingFeatureEnabled.value) await refreshRecordingHistory()
}
function buildRunPayload(actionControlId: string): PlayerRuntimeRunPayload {
    const profile = profiles.value.find((item) => item.profile_id === selectedProfileId.value)
    const targetOverride = !profile || targetId.value !== profile.target_id
    return {
        ...(targetOverride ? { target_id: targetId.value } : {}),
        profile_id: profile?.profile_id,
        profile_revision: profile?.revision,
        player_values: runValueOverrides(),
        action_control_id: actionControlId,
    }
}
async function executePreparedRun(payload: PlayerRuntimeRunPayload) {
    const session = await vnextApi.playerRuntimeRun(payload)
    await follow(session)
}
async function start(actionControlId = '') {
    if (isActive.value || pendingDangerousRun.value) return
    operationError.value = ''
    serviceDisconnected.value = false
    lastActionControlId = actionControlId
    clearedThrough.value = 0
    try {
        if (!runtimeMode.value) throw new Error('没有已加载的已发布 Player 项目')
        const payload = buildRunPayload(actionControlId)
        const { operations } = await vnextApi.playerRuntimeDangerousOperations(payload)
        if (operations.length) {
            pendingDangerousRun.value = { payload, operations }
            return
        }
        await executePreparedRun(payload)
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '运行失败'
    }
}
function cancelDangerousRun() {
    if (confirmingDangerousRun.value) return
    pendingDangerousRun.value = null
}
async function confirmDangerousRun() {
    const pending = pendingDangerousRun.value
    if (!pending || confirmingDangerousRun.value) return
    confirmingDangerousRun.value = true
    operationError.value = ''
    try {
        pendingDangerousRun.value = null
        await executePreparedRun({
            ...pending.payload,
            dangerous_confirmations: pending.operations.map((operation) => ({
                confirmation_id: operation.confirmation_id,
                confirmed: true as const,
            })),
        })
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '运行失败'
    } finally {
        confirmingDangerousRun.value = false
    }
}
async function runMain() {
    await start()
}
async function runAction(id: string) {
    await start(id)
}
async function stop() {
    if (!execution.value) return
    const current = execution.value
    followToken += 1
    try {
        execution.value = await vnextApi.cancelRun(current.execution_id)
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '停止运行失败'
    }
}
async function completePlayerClose(stopActive: boolean) {
    if (closingPlayer.value) return
    closingPlayer.value = true
    operationError.value = ''
    try {
        if (stopActive && isActive.value && execution.value) {
            const executionId = execution.value.execution_id
            followToken += 1
            execution.value = await vnextApi.cancelRun(executionId)
            const deadline = Date.now() + 5_000
            while (isActive.value && Date.now() < deadline) {
                await new Promise((resolve) => setTimeout(resolve, 100))
                execution.value = mergeRuntimeSession(execution.value, await vnextApi.runStatus(executionId))
            }
            if (isActive.value) throw new Error('脚本仍在停止中，请稍后重试关闭')
        }
        if (playerRecording.value?.active) {
            playerRecording.value = await vnextApi.stopPlayerRuntimeRecording()
            if (playerRecording.value?.active) throw new Error('运行录制仍在停止中，请稍后重试关闭')
        }
        if (activeCapture.value && !await cancelActiveCapture()) {
            throw new Error(operationError.value || '字段采集仍在结束中，请稍后重试关闭')
        }
        pendingPlayerClose.value = false
        if (!await sendNativeWindowCommand('close-confirmed')) {
            throw new Error('原生窗口连接不可用，Player 尚未关闭')
        }
    } catch (value) {
        pendingPlayerClose.value = false
        await sendNativeWindowCommand('close-cancelled')
        operationError.value = value instanceof Error ? `无法安全退出：${value.message}` : '无法安全退出 Player'
    } finally {
        closingPlayer.value = false
    }
}
async function requestPlayerClose() {
    if (closingPlayer.value || pendingPlayerClose.value) return
    if (isActive.value) {
        pendingPlayerClose.value = true
        return
    }
    await completePlayerClose(false)
}
function cancelPlayerClose() {
    if (closingPlayer.value) return
    pendingPlayerClose.value = false
    void sendNativeWindowCommand('close-cancelled')
}
async function confirmPlayerClose() {
    await completePlayerClose(true)
}
async function stopRecording() {
    try {
        playerRecording.value = await vnextApi.stopPlayerRuntimeRecording()
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '停止录制失败'
    }
}
async function pause() {
    if (!execution.value || execution.value.status !== 'running') return
    try {
        execution.value = mergeRuntimeSession(execution.value, await vnextApi.pauseRun(execution.value.execution_id))
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '暂停运行失败'
    }
}
async function resume() {
    if (!execution.value || execution.value.status !== 'paused') return
    try {
        execution.value = mergeRuntimeSession(execution.value, await vnextApi.resumeRun(execution.value.execution_id))
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '继续运行失败'
    }
}
async function retry() {
    await start(lastActionControlId)
}
async function copyLogs() {
    const text = visibleEvents.value.map((event) => `[${event.timestamp.slice(11, 19)}] ${event.message}`).join('\n')
    try {
        await navigator.clipboard.writeText(text)
    } catch {
        operationError.value = '无法访问剪贴板，请检查系统权限'
    }
}
function clearLogs() {
    clearedThrough.value = Math.max(0, ...visibleEvents.value.map((event) => event.sequence))
}
function reloadAppliedContent() {
    if (!isActive.value && !hasUncommittedDraft.value) window.location.reload()
}
function readFile(file: File) {
    return new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onerror = () => reject(new Error('读取图片失败'))
        reader.onload = () =>
            resolve(
                String(reader.result || '')
                    .split(',')
                    .pop() || ''
            )
        reader.readAsDataURL(file)
    })
}
function upsertProfile(profile: PlayerProfile) {
    profiles.value = [...profiles.value.filter((item) => item.profile_id !== profile.profile_id), profile]
        .sort((left, right) => left.name.localeCompare(right.name, 'zh-CN'))
    if (profile.profile_id === selectedProfileId.value) loadRecordingDraft(profile.recording)
}
async function refreshRuntimeAssets() {
    try {
        const runtime = await vnextApi.playerRuntimeBootstrap()
        assets.value = runtime.assets?.assets || assets.value
    } catch { /* The captured value remains valid; the next bootstrap refreshes labels. */ }
}
async function beginTerminalAction(action: PlayerTerminalActionAvailability) {
    if (!action.enabled || interactionLocked.value) return
    // A terminal capture leaves the WebView and may later return to the same
    // field. Drop the old focus first so Android does not reopen its keyboard
    // over the freshly captured value.
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
    operationError.value = ''
    if (action.destination.product_id !== productId.value || action.destination.release_id !== releaseId.value) {
        operationError.value = '终端字段操作属于旧发布，请重新载入 Player'
        return
    }
    try {
        const started = await vnextApi.startPlayerControlCapture(action.destination, window.location.origin)
        if (started.cancelled || started.state === 'cancelled') {
            activeCapture.value = null
            pendingCaptureResult.value = null
            await refreshTerminalActions()
            return
        }
        activeCapture.value = {
            capture_id: started.capture_id,
            destination: started.destination,
            state: started.state,
            ...(started.candidate ? { candidate: started.candidate } : {}),
        }
        pendingCaptureResult.value = started.candidate
            ? { kind: 'native-reference', candidate_id: started.candidate.candidate_id }
            : null
        if (started.candidate) await confirmPendingCapture()
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '终端字段采集启动失败'
        await refreshTerminalActions()
    }
}
async function chooseCaptureFile() {
    const active = activeCapture.value
    if (!active || active.destination.action_id !== 'choose-resource' || captureCompleting) return
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/png,image/jpeg,image/bmp,image/webp'
    input.oncancel = () => cancelActiveCapture()
    input.onchange = async () => {
        const file = input.files?.[0]
        if (!file) {
            await cancelActiveCapture()
            return
        }
        try {
            const content = await readFile(file)
            pendingCaptureResult.value = { kind: 'file', file_name: file.name, content_base64: content }
            activeCapture.value = {
                ...active,
                state: 'awaiting_confirmation',
                candidate: { candidate_id: '', kind: 'file', display_name: file.name, access: [] },
            }
            await confirmPendingCapture()
        } catch (value) {
            operationError.value = value instanceof Error ? value.message : '读取图片失败'
        }
    }
    input.click()
}
async function confirmPendingCapture() {
    if (!pendingCaptureResult.value) return
    await confirmActiveCapture(pendingCaptureResult.value)
}
async function confirmActiveCapture(result: Record<string, unknown>) {
    const active = activeCapture.value
    if (!active || captureCompleting) return { ok: false, message: '终端字段采集会话已结束' }
    captureCompleting = true
    try {
        const confirmed = await vnextApi.confirmPlayerControlCapture(
            active.capture_id, active.destination, result,
        )
        upsertProfile(confirmed.profile)
        values[active.destination.control_id] = structuredClone(confirmed.value)
        baselineValues.value = {
            ...baselineValues.value,
            [active.destination.control_id]: structuredClone(confirmed.value),
        }
        activeCapture.value = null
        pendingCaptureResult.value = null
        await Promise.allSettled([refreshRuntimeAssets(), refreshTerminalActions()])
        await presentHostFeedback({
            ok: true,
            message: '字段已采集并保存',
            control_id: active.destination.control_id,
        })
        return { ok: true }
    } catch (value) {
        const message = value instanceof Error ? value.message : '终端字段确认失败'
        operationError.value = message
        await vnextApi.cancelPlayerControlCapture(active.capture_id, active.destination).catch(() => undefined)
        activeCapture.value = null
        pendingCaptureResult.value = null
        await refreshTerminalActions()
        return { ok: false, message }
    } finally {
        captureCompleting = false
    }
}
async function cancelActiveCapture() {
    const active = activeCapture.value
    if (!active || captureCompleting) return false
    captureCompleting = true
    try {
        await vnextApi.cancelPlayerControlCapture(active.capture_id, active.destination)
        activeCapture.value = null
        pendingCaptureResult.value = null
        await refreshTerminalActions()
        return true
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '取消终端字段采集失败'
        return false
    } finally {
        captureCompleting = false
    }
}
async function restoreProfileImage(controlId: string) {
    const action = terminalActionsFor(controlId).find((item) =>
        item.enabled && ['choose-resource', 'capture-image'].includes(item.action_id),
    )
    if (!action) {
        operationError.value = '当前发布或宿主不允许恢复这个图片字段'
        return
    }
    try {
        const restored = await vnextApi.restorePlayerProfileImage(action.destination)
        upsertProfile(restored.profile)
        values[controlId] = structuredClone(restored.value)
        baselineValues.value = { ...baselineValues.value, [controlId]: structuredClone(restored.value) }
        await Promise.allSettled([refreshRuntimeAssets(), refreshTerminalActions()])
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : '恢复默认图片失败'
    }
}
async function handleCaptureEvent(event: MessageEvent) {
    let data: Record<string, unknown>
    try { data = JSON.parse(String(event.data || '{}')) }
    catch { return }
    const active = activeCapture.value
    if (!active) return
    if (data.event === 'copy' && active.destination.action_id === 'capture-control') {
        if (String(data.field_request_id || '') !== active.capture_id) return
        await confirmActiveCapture({ kind: 'control', selector: data.selector, info: data.info })
        return
    }
    if (data.event === 'mode' && data.active === false && active.destination.action_id === 'capture-control' && String(data.field_request_id || '') === active.capture_id && !captureCompleting) {
        await cancelActiveCapture()
        return
    }
    if (data.event === 'screenshot-error' && active.destination.action_id !== 'capture-control') {
        operationError.value = String(data.message || '原生采集宿主失败')
        await cancelActiveCapture()
        return
    }
    if (data.event !== 'capture-command' || String(data.field_request_id || '') !== active.capture_id) return
    let acknowledge: Record<string, unknown> = { ok: false, message: '终端字段采集会话已失效' }
    if (data.kind === 'field_cancel') acknowledge = { ok: await cancelActiveCapture() }
    else if (data.kind === 'field_confirm') acknowledge = await confirmActiveCapture(data)
    await vnextApi.acknowledgeCaptureAction(String(data.request_id || ''), acknowledge).catch(() => undefined)
}
function connectCaptureEvents() {
    if (window.EasyCodeAndroid) {
        window.addEventListener('easycode-native-capture-complete', handleAndroidCaptureComplete)
        return
    }
    if (captureEventSource || typeof EventSource === 'undefined') return
    captureEventSource = new EventSource('/api/ui-control/events')
    captureEventSource.onmessage = (event) => { void handleCaptureEvent(event) }
    captureEventSource.onerror = () => {
        if (activeCapture.value) operationError.value = '与原生采集宿主的事件连接已中断，正在重连'
    }
}
async function handleAndroidCaptureComplete(event: Event) {
    const detail = (event as CustomEvent<{ ok: boolean; message?: string; control_id?: string }>).detail
    const message = detail?.message || (detail?.ok ? '字段已采集并保存' : 'Android 字段采集未完成，旧值保持不变')
    await presentHostFeedback({ ok: Boolean(detail?.ok), message, control_id: detail?.control_id })
    activeCapture.value = null
    pendingCaptureResult.value = null
    try {
        const runtime = await vnextApi.playerRuntimeBootstrap()
        const nextProfiles = await vnextApi.playerRuntimeProfiles()
        assets.value = runtime.assets?.assets || assets.value
        profiles.value = nextProfiles.profiles
        const current = profiles.value.find((item) => item.profile_id === selectedProfileId.value) || profiles.value[0]
        selectedProfileId.value = current?.profile_id || ''
        applySelectedProfile()
        await refreshTerminalActions()
    } catch (value) {
        operationError.value = value instanceof Error ? value.message : 'Android 采集完成后无法刷新配置方案'
    }
}
async function presentHostFeedback(detail?: { ok: boolean; message: string; control_id?: string }) {
    if (!detail?.message) return
    // Terminal field outcomes belong to the shared Player feedback surface, not
    // the persistent task error panel or a host-native toast.
    operationError.value = ''
    showFeedback(detail.message, detail.ok ? 'success' : 'error')
    if (!detail.control_id) return
    const page = playerForm.value.pages.find((candidate) =>
        candidate.controls.some((control) => control.control_id === detail.control_id),
    )
    if (page) activePageId.value = page.page_id
    await nextTick()
    // Returning from a native picker/capture must not reopen the soft keyboard.
    // Keep orientation through scroll + a short visual pulse instead of focus().
    if (document.activeElement instanceof HTMLElement) document.activeElement.blur()
    const field = Array.from(document.querySelectorAll<HTMLElement>('[data-control-id]'))
        .find((candidate) => candidate.dataset.controlId === detail.control_id)
    if (!field) return
    field.scrollIntoView({ block: 'center', behavior: 'smooth' })
    field.classList.remove('capture-return-highlight')
    // Force a fresh animation when consecutive capture results target the same
    // field, while making the orientation cue visible immediately after return.
    void field.offsetWidth
    field.classList.add('capture-return-highlight')
    window.setTimeout(() => field.classList.remove('capture-return-highlight'), 1800)
}
function dismissFeedback() {
    if (feedbackTimer) clearTimeout(feedbackTimer)
    feedbackTimer = null
    feedback.message = ''
}
function showFeedback(message: string, tone: 'success' | 'error') {
    dismissFeedback()
    feedback.message = message
    feedback.tone = tone
    feedbackTimer = setTimeout(() => {
        feedback.message = ''
        feedbackTimer = null
    }, tone === 'error' ? 7000 : 3600)
}
onMounted(async () => {
    window.addEventListener('message', handleConsoleCommand)
    let startupHostFeedback: { ok: boolean; message: string; control_id?: string } | undefined
    try {
        const runtime = await vnextApi.playerRuntimeBootstrap()
        if (!runtime.available || !runtime.form) throw new Error('没有可运行的已发布 Player 项目')
        runtimeMode.value = true
        playerForm.value = runtime.form
        targets.value = runtime.targets || []
        assets.value = runtime.assets?.assets || []
        defaultTargetId.value = runtime.default_target_id || null
        targetId.value = defaultTargetId.value
        projectName.value = runtime.bundle?.name || 'EasyCode Player'
        productId.value = runtime.bundle?.project_id || ''
        releaseId.value = runtime.bundle?.release_id || ''
        playerUpdates.value = runtime.updates || null
        startupHostFeedback = runtime.host_feedback
        connectCaptureEvents()
        try {
            profiles.value = (await vnextApi.playerRuntimeProfiles()).profiles
        } catch (value) {
            operationError.value = value instanceof Error ? value.message : '配置方案加载失败'
        }
        activePageId.value = playerForm.value.pages[0]?.page_id || ''
        selectInitialProfile()
        await refreshTerminalActions()
        if (recordingFeatureEnabled.value) await refreshRecordingHistory()
    } catch (value) {
        startupError.value = value instanceof Error ? value.message : 'Player 初始化失败'
    } finally {
        loading.value = false
    }
    if (!startupError.value) {
        await presentHostFeedback(startupHostFeedback)
        if (consoleParentOrigin && window.parent !== window) {
            window.parent.postMessage({ event: 'easycode-player-ready', version: 1 }, consoleParentOrigin)
        }
    }
})
watch(
    [selectedProfileId, targetId, () => selectedProfile.value?.revision || 0, isActive],
    () => { void refreshTerminalActions() },
)
onBeforeUnmount(() => {
    disposed = true
    dismissFeedback()
    followToken += 1
    captureEventSource?.close()
    captureEventSource = null
    window.removeEventListener('easycode-native-capture-complete', handleAndroidCaptureComplete)
    window.removeEventListener('message', handleConsoleCommand)
    if (activeCapture.value) {
        const active = activeCapture.value
        void vnextApi.cancelPlayerControlCapture(active.capture_id, active.destination).catch(() => undefined)
    }
})
</script>

<style scoped>
.player-app {
    --app-text-placeholder: #83837b;
    width: 100vw;
    height: 100vh;
    display: grid;
    grid-template-rows: var(--app-height-app-header) minmax(0, 1fr);
    overflow: hidden;
    background: var(--app-bg-base);
    color: var(--app-text-regular);
}
.player-app.is-embedded { grid-template-rows: minmax(0, 1fr); }
.application-icon {
    width: 20px;
    height: 20px;
    flex: 0 0 20px;
    border-radius: var(--app-radius-sm);
    object-fit: cover;
}
.layout {
    position: relative;
    min-width: 0;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(360px, 1fr) 5px var(--runtime-panel-width, 320px);
    grid-template-rows: auto minmax(0, 1fr);
    overflow: hidden;
}
.layout.runtime-collapsed { grid-template-columns: minmax(360px, 1fr); }
.layout.content-collapsed { grid-template-columns: minmax(0, 1fr); }
.layout.without-nav {
    grid-template-rows: minmax(0, 1fr);
}
.page-tabs { grid-column: 1; grid-row: 1; }
.mobile-context { display: none; }
.content {
    grid-column: 1;
    grid-row: 2;
    min-width: 0;
    min-height: 0;
    overflow-x: hidden;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 28px;
}
.without-nav .content { grid-row: 1; }
.runtime-panel { grid-column: 3; grid-row: 1 / -1; }
.runtime-panel-resizer { grid-column: 2; grid-row: 1 / -1; }
.runtime-panel-restore { position: absolute; z-index: 4; top: 8px; right: 8px; }
.layout.content-collapsed .runtime-panel { grid-column: 1; }
.runtime-form {
    max-width: 860px;
    display: grid;
    grid-template-columns: repeat(12, minmax(0, 1fr));
    gap: var(--app-form-field-gap);
    margin: 0 auto;
}
.runtime-form > label.capture-return-highlight {
    border-radius: 9px;
    outline: 2px solid color-mix(in srgb, var(--app-color-primary) 72%, transparent);
    outline-offset: 6px;
    animation: capture-return-pulse 1.8s ease-out both;
}
@keyframes capture-return-pulse {
    0% { background: color-mix(in srgb, var(--app-color-primary) 16%, transparent); }
    100% { background: transparent; }
}
.runtime-form > label {
    grid-column: span 12;
    display: flex;
    flex-direction: column;
    gap: var(--app-form-label-control-gap);
    color: var(--app-text-regular);
    font-size: var(--app-font-compact);
}
.runtime-form > label.is-inline-field {
    display: grid;
    grid-template-columns: minmax(96px, 132px) minmax(0, 1fr) auto;
    align-items: center;
    column-gap: 10px;
    row-gap: var(--app-form-label-control-gap);
}
.runtime-form > label.is-inline-field > span:first-child {
    min-width: 0;
}
.runtime-form > label.is-inline-field > small {
    grid-column: 2 / -1;
}
.runtime-form > label.is-inline-field > .terminal-actions {
    grid-column: 3;
}
.runtime-form > label.span-6 {
    grid-column: span 6;
}
.runtime-form > label.span-4 {
    grid-column: span 4;
}
.runtime-form label > span:first-child {
    color: var(--app-text-secondary);
}
.runtime-form b {
    color: var(--app-color-danger);
}
.runtime-form input:not([type='checkbox']),
.runtime-form select,
.runtime-panel select {
    height: var(--app-control-default);
    padding: 0 10px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-md);
    outline: 0;
    background: var(--app-bg-input);
    color: var(--app-text-primary);
}
.runtime-form input:focus,
.runtime-form select:focus,
.runtime-panel select:focus {
    border-color: var(--app-color-primary);
    box-shadow: var(--focus-ring);
}
.runtime-form small {
    color: var(--app-text-placeholder);
    font-size: var(--app-font-caption);
}
.terminal-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 5px;
}
.terminal-actions button,
.terminal-actions summary {
    height: 27px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 0 7px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
    cursor: pointer;
}
.terminal-actions details {
    position: relative;
}
.terminal-actions summary {
    list-style: none;
}
.terminal-actions details[open] {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
}
.terminal-actions button:hover:not(:disabled),
.terminal-actions summary:hover {
    background: var(--app-bg-hover);
    color: var(--app-text-primary);
}
.terminal-actions button:disabled {
    cursor: not-allowed;
    opacity: .52;
}
.terminal-action-reason {
    flex-basis: 100%;
    line-height: 1.4;
}
.capture-progress {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    color: var(--app-text-secondary);
}
.capture-candidate {
    min-width: 0;
    display: inline-flex;
    align-items: center;
    gap: 5px;
}
.capture-candidate > span {
    max-width: 180px;
    overflow: hidden;
    color: var(--app-text-primary);
    text-overflow: ellipsis;
    white-space: nowrap;
}
.capture-candidate .capture-use {
    border-color: var(--app-color-primary);
    color: var(--app-color-primary);
}
.toggle {
    width: 36px;
    height: 21px;
    position: relative;
}
.toggle input {
    position: absolute;
    opacity: 0;
}
.toggle i {
    display: block;
    width: 36px;
    height: 21px;
    border-radius: 11px;
    background: var(--app-border-default);
}
.toggle input:checked + i {
    background: var(--app-color-primary);
}
.runtime-panel {
    min-width: 0;
    min-height: 0;
    display: flex;
    flex-direction: column;
    padding: 14px;
    border-left: 1px solid var(--app-border-subtle);
    background: var(--app-bg-sidebar);
    overflow-x: hidden;
    overflow-y: auto;
    overscroll-behavior: contain;
}
.runtime-panel > header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: 14px;
}
.runtime-heading-actions { display: flex; align-items: center; gap: 3px; }
.runtime-panel strong {
    color: var(--app-text-primary);
    font-size: var(--app-font-body);
}
.runtime-panel header span {
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
}
.runtime-panel > label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
}
.runtime-tools {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
    padding: 10px;
    border: 1px solid var(--app-border-subtle);
    border-radius: var(--app-radius-md);
    background: var(--app-bg-input);
}
.support-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 6px;
    margin-bottom: 10px;
}
.tool-heading,
.environment-report > span,
.log-heading,
.log-heading > span {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 6px;
}
.tool-heading button,
.profile-actions button,
.log-heading button,
.result-actions button,
.result-actions a {
    height: 26px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    padding: 0 7px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
    text-decoration: none;
    cursor: pointer;
}
.tool-heading button:hover,
.profile-actions button:hover,
.log-heading button:hover,
.result-actions button:hover,
.result-actions a:hover {
    background: var(--app-bg-hover);
    color: var(--app-text-primary);
}
.runtime-tools label {
    display: flex;
    flex-direction: column;
    gap: 5px;
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
}
.environment-report {
    padding: 7px 8px;
    border: 1px solid color-mix(in srgb, var(--app-color-danger) 45%, var(--app-border-subtle));
    border-radius: var(--app-radius-sm);
    background: color-mix(in srgb, var(--app-color-danger) 7%, transparent);
}
.environment-report.ready {
    border-color: color-mix(in srgb, var(--app-color-success) 45%, var(--app-border-subtle));
    background: color-mix(in srgb, var(--app-color-success) 7%, transparent);
}
.environment-report span {
    color: var(--app-text-primary);
    font-size: var(--app-font-caption);
}
.environment-report small {
    color: var(--app-text-placeholder);
    font-size: var(--app-font-caption);
}
.environment-report p {
    margin: 4px 0 0;
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
    line-height: 15px;
}
.environment-report p.fail { color: var(--app-color-danger); }
.environment-report p.warning { color: var(--app-color-warning); }
.profile-actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 28px 28px;
    gap: 5px;
}
.profile-actions input {
    min-width: 0;
    height: var(--app-control-compact);
    padding: 0 8px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    outline: none;
    background: var(--app-bg-base);
    color: var(--app-text-primary);
    font-size: var(--app-font-caption);
}
.profile-notice {
    display: grid;
    grid-template-columns: 14px minmax(0, 1fr);
    align-items: start;
    gap: 6px;
    margin: 0;
    padding: 7px 8px;
    border: 1px solid color-mix(in srgb, var(--app-color-warning) 34%, var(--app-border-subtle));
    border-radius: var(--app-radius-sm);
    background: color-mix(in srgb, var(--app-color-warning) 6%, transparent);
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
    line-height: 15px;
}
.profile-notice svg {
    margin-top: 1px;
    color: var(--app-color-warning);
}
.recording-settings {
    border-top: 1px solid var(--app-border-subtle);
    padding-top: 8px;
}
.recording-settings summary {
    min-height: var(--app-control-compact);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    color: var(--app-text-primary);
    cursor: pointer;
}
.recording-settings summary span,
.recording-runtime > span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}
.recording-settings summary em {
    color: var(--app-text-placeholder);
    font-size: var(--app-font-caption);
    font-style: normal;
}
.recording-toggle {
    display: grid !important;
    grid-template-columns: auto minmax(0, 1fr);
    align-items: start;
    gap: 7px !important;
    padding: 7px 0;
    color: var(--app-text-regular) !important;
    line-height: 14px;
}
.recording-toggle input { margin: 1px 0 0; accent-color: var(--app-color-primary); }
.recording-fields {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 7px;
    padding: 5px 0 7px;
}
.recording-fields input,
.recording-fields select {
    width: 100%;
    min-width: 0;
    height: var(--app-control-compact);
    padding: 0 7px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    outline: none;
    background: var(--app-bg-base);
    color: var(--app-text-primary);
    font-size: var(--app-font-caption);
}
.recording-fields label:first-child { grid-column: 1 / -1; }
.recording-settings > small,
.recording-note {
    display: block;
    margin: 4px 0 0;
    color: var(--app-text-placeholder);
    font-size: var(--app-font-caption);
    line-height: 15px;
}
.recording-note.warning { color: var(--app-color-warning); }
.recording-runtime {
    position: relative;
    margin-bottom: 10px;
    padding: 9px 10px;
    border: 1px solid color-mix(in srgb, var(--app-color-primary) 40%, var(--app-border-default));
    border-radius: var(--app-radius-md);
    background: color-mix(in srgb, var(--app-color-primary) 6%, var(--app-bg-input));
    font-size: var(--app-font-caption);
}
.recording-runtime p {
    margin: 5px 0 0;
    color: var(--app-text-secondary);
    line-height: 14px;
}
.recording-runtime button {
    margin-top: 7px;
    height: 25px;
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 0 7px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
    cursor: pointer;
}
.recording-history-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 9px;
    padding-top: 7px;
    border-top: 1px solid var(--app-border-subtle);
    color: var(--app-text-primary);
    font-size: var(--app-font-caption);
}
.recording-history-heading button,
.recording-session-row,
.recording-viewer button {
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    cursor: pointer;
}
.recording-history-heading button { display: inline-flex; align-items: center; gap: 4px; height: 25px; padding: 0 7px; font-size: var(--app-font-caption); }
.recording-empty { margin: 7px 0 0; color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.recording-session-row {
    width: 100%;
    min-height: 38px;
    margin-top: 5px;
    padding: 5px 7px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    text-align: left;
}
.recording-session-row > span { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.recording-session-row strong { color: var(--app-text-primary); font-size: var(--app-font-caption); font-weight: 550; }
.recording-session-row small { overflow: hidden; color: var(--app-text-placeholder); font-size: var(--app-font-caption); text-overflow: ellipsis; white-space: nowrap; }
.recording-session-row em { flex: 0 0 auto; color: var(--app-text-secondary); font-size: var(--app-font-caption); font-style: normal; }
.recording-viewer-backdrop {
    position: fixed;
    inset: 0;
    z-index: 120;
    display: grid;
    place-items: center;
    padding: 12px;
    background: rgb(0 0 0 / 72%);
}
.recording-viewer {
    width: min(760px, 100%);
    max-height: calc(100vh - 24px);
    display: grid;
    grid-template-rows: auto minmax(160px, 1fr) auto;
    overflow: hidden;
    border: 1px solid var(--app-border-strong);
    border-radius: 9px;
    background: var(--app-bg-raised);
    box-shadow: 0 18px 50px rgb(0 0 0 / 44%);
}
.recording-viewer header,
.recording-viewer footer { display: flex; align-items: center; gap: 7px; padding: 9px 10px; }
.recording-viewer header { justify-content: space-between; border-bottom: 1px solid var(--app-border-subtle); }
.recording-viewer header > span { display: flex; flex-direction: column; gap: 2px; }
.recording-viewer header small { color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.recording-viewer header button { width: 28px; height: var(--app-control-compact); display: grid; place-items: center; }
.recording-frame-stage { min-height: 0; display: grid; place-items: center; overflow: auto; background: #080808; }
.recording-frame-stage img { display: block; max-width: 100%; max-height: 70vh; object-fit: contain; }
.recording-frame-stage p { color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
.recording-viewer footer { border-top: 1px solid var(--app-border-subtle); }
.recording-viewer footer button { min-height: var(--app-control-compact); display: inline-flex; align-items: center; gap: 3px; padding: 0 8px; }
.recording-viewer footer span { color: var(--app-text-secondary); font-size: var(--app-font-caption); }
.recording-viewer footer .danger-text { margin-left: auto; color: var(--app-color-danger); }
.recording-history-heading button:hover:not(:disabled),
.recording-session-row:hover:not(:disabled),
.recording-viewer button:hover:not(:disabled) { border-color: var(--app-border-strong); background: var(--app-bg-hover); color: var(--app-text-primary); }
@media (max-width: 480px) {
    .recording-viewer footer { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .recording-viewer footer > span { grid-column: 1 / -1; grid-row: 1; justify-self: center; order: -1; }
    .recording-viewer footer button { justify-content: center; white-space: nowrap; }
    .recording-viewer footer .danger-text { margin-left: 0; }
}
.runtime-error {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: start;
    gap: 8px;
    margin-bottom: 12px;
    padding: 9px 10px;
    border: 1px solid color-mix(in srgb, var(--app-color-danger) 45%, var(--app-border-default));
    border-radius: var(--app-radius-md);
    background: color-mix(in srgb, var(--app-color-danger) 10%, var(--app-bg-input));
    color: var(--app-text-regular);
    font-size: var(--app-font-caption);
    line-height: 15px;
}
.runtime-error > svg {
    margin-top: 1px;
    color: var(--app-color-danger);
}
.runtime-error button {
    width: 24px;
    height: 24px;
    display: grid;
    place-items: center;
    margin: -5px -6px 0 0;
    padding: 0;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
    cursor: pointer;
}
.runtime-error button:hover {
    background: var(--app-bg-hover);
    color: var(--app-text-primary);
}
.actions {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    padding: 14px 0;
}
.primary,
.secondary,
.danger {
    height: var(--app-control-default);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 0 12px;
    border: 1px solid var(--app-color-primary);
    border-radius: var(--app-radius-md);
    background: var(--app-color-primary);
    color: #fff;
    cursor: pointer;
}
.secondary {
    align-self: flex-start;
    background: transparent;
    color: var(--app-color-primary);
}
.danger {
    border-color: var(--app-color-danger);
    background: transparent;
    color: var(--app-color-danger);
}
.result-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    padding: 0 0 10px;
}
.log-heading {
    min-height: var(--app-control-compact);
    border-top: 1px solid var(--app-border-subtle);
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
}
.log-heading button {
    width: 25px;
    padding: 0;
    border: 0;
}
.runtime-log {
    min-height: 0;
    flex: 1;
    overflow: auto;
    padding-top: 2px;
}
.runtime-log > div {
    display: grid;
    grid-template-columns: 58px minmax(0, 1fr);
    gap: 7px;
    padding: 5px 2px;
    font-family: var(--app-font-mono);
    font-size: var(--app-font-caption);
}
.runtime-log time,
.runtime-log p {
    color: var(--app-text-placeholder);
}
.runtime-log span {
    color: var(--app-text-regular);
    line-height: 15px;
}
.danger-operation-list {
    max-height: 230px;
    overflow: auto;
    margin: 0;
    padding: 0;
    list-style: none;
}
.danger-operation-list li {
    display: grid;
    grid-template-columns: 110px minmax(0, 1fr);
    gap: 10px;
    align-items: center;
    padding: 8px 0;
    border-bottom: 1px solid var(--app-border-subtle);
    font-size: var(--app-font-caption);
}
.danger-operation-list li:last-child {
    border-bottom: 0;
}
.danger-operation-list code {
    overflow: hidden;
    color: var(--app-text-regular);
    font-family: var(--app-font-mono);
    text-overflow: ellipsis;
    white-space: nowrap;
}
.danger-operation-note {
    margin: 8px 0 0;
    padding: 10px;
    border-radius: var(--app-radius-sm);
    background: color-mix(in srgb, var(--app-color-danger) 8%, transparent);
    color: var(--app-text-secondary);
    font-size: var(--app-font-caption);
    line-height: 16px;
}
.state {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    color: var(--app-text-secondary);
    text-align: center;
}
.state strong {
    color: var(--app-text-primary);
    font-size: var(--app-font-compact);
}
.state p {
    max-width: 440px;
    margin: 0;
    font-size: var(--app-font-caption);
    line-height: 16px;
}
.state.error svg {
    color: var(--app-color-danger);
}
.spin {
    animation: spin 0.8s linear infinite;
}
.player-feedback {
    position: fixed;
    z-index: 1300;
    right: 18px;
    bottom: 18px;
    max-width: min(420px, calc(100vw - 36px));
    min-height: 42px;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 9px;
    padding: 10px 10px 10px 12px;
    border: 1px solid var(--app-border-default);
    border-radius: var(--app-radius-lg);
    background: var(--app-bg-raised);
    box-shadow: 0 12px 32px rgba(0, 0, 0, .3);
    color: var(--app-text-primary);
    font-size: var(--app-font-caption);
    line-height: 16px;
}
.player-feedback.success > svg { color: var(--app-color-success); }
.player-feedback.error > svg { color: var(--app-color-danger); }
.player-feedback button {
    width: 30px;
    height: var(--app-control-compact);
    display: grid;
    place-items: center;
    padding: 0;
    border: 0;
    border-radius: var(--app-radius-sm);
    background: transparent;
    color: var(--app-text-secondary);
}
.player-feedback button:hover { background: var(--app-bg-hover); color: var(--app-text-primary); }
@keyframes spin {
    to {
        transform: rotate(360deg);
    }
}
@media (max-width: 760px) {
    .player-app {
        min-height: 100dvh;
        height: 100dvh;
        grid-template-rows: auto minmax(0, 1fr);
    }
    .titlebar {
        min-height: 52px;
        padding: max(8px, env(safe-area-inset-top)) 16px 8px;
    }
    .titlebar strong { font-size: var(--app-font-page-title); }
    .titlebar > span {
        max-width: 42vw;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .layout,
    .layout.without-nav {
        display: block;
        overflow: auto;
    }
    .runtime-panel-resizer { display: none; }
    .mobile-context {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 8px;
        align-items: end;
        padding: 14px 16px;
        border-bottom: 1px solid var(--app-border-subtle);
        background: var(--app-bg-sidebar);
    }
    .mobile-context label { display: grid; gap: 6px; color: var(--app-text-secondary); font-size: var(--app-font-caption); }
    .mobile-context select,
    .mobile-context button {
        min-width: 0;
        height: 44px;
        padding: 0 12px;
        border: 1px solid var(--app-border-default);
        border-radius: 9px;
        outline: 0;
        background: var(--app-bg-input);
        color: var(--app-text-primary);
        font-size: var(--app-font-body);
    }
    .mobile-context button { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
    .mobile-context small { grid-column: 1 / -1; color: var(--app-text-placeholder); font-size: var(--app-font-caption); }
    .android-host .titlebar > span { display: none; }
    .content {
        overflow: visible;
        padding: 22px 16px 28px;
    }
    .runtime-panel {
        min-height: auto;
        overflow: visible;
    }
    .runtime-form { gap: 20px; }
    .runtime-form > label { gap: 8px; font-size: var(--app-font-body); }
    .runtime-form > label.is-inline-field {
        grid-template-columns: minmax(0, 1fr);
        align-items: stretch;
        row-gap: 8px;
    }
    .runtime-form > label.is-inline-field > small,
    .runtime-form > label.is-inline-field > .terminal-actions {
        grid-column: 1;
    }
    .runtime-form small { font-size: var(--app-font-caption); line-height: 17px; }
    .runtime-form input:not([type='checkbox']),
    .runtime-form select,
    .runtime-panel select { height: 44px; font-size: var(--app-font-page-title); }
    .terminal-actions { gap: 8px; }
    .terminal-actions button,
    .terminal-actions summary {
        min-height: 44px;
        height: 44px;
        padding: 0 12px;
        border-radius: var(--app-radius-md);
        font-size: var(--app-font-compact);
    }
    .runtime-panel {
        gap: 4px;
        padding: 18px 16px calc(92px + env(safe-area-inset-bottom));
        border-left: 0;
        border-top: 1px solid var(--app-border-subtle);
    }
    .runtime-tools { padding: 12px; border-radius: var(--app-radius-lg); }
    .runtime-tools label,
    .runtime-panel > label { font-size: var(--app-font-compact); }
    .profile-actions { grid-template-columns: minmax(0, 1fr) 44px 44px; gap: 8px; }
    .profile-actions input,
    .profile-actions button,
    .tool-heading button,
    .result-actions button,
    .result-actions a { min-height: 44px; height: 44px; font-size: var(--app-font-compact); }
    .actions {
        position: fixed;
        z-index: 12;
        right: 0;
        bottom: 0;
        left: 0;
        display: grid;
        grid-auto-flow: column;
        grid-auto-columns: minmax(0, 1fr);
        gap: 8px;
        margin: 0;
        padding: 10px 16px max(10px, env(safe-area-inset-bottom));
        border-top: 1px solid var(--app-border-subtle);
        background: color-mix(in srgb, var(--app-bg-chrome) 94%, transparent);
        box-shadow: 0 -12px 28px rgba(0, 0, 0, .24);
    }
    .primary,
    .secondary,
    .danger { width: 100%; height: 46px; border-radius: 9px; font-size: var(--app-font-body); }
    .runtime-log { min-height: 180px; max-height: 42dvh; }
    .player-feedback {
        right: 16px;
        bottom: calc(78px + env(safe-area-inset-bottom));
        left: 16px;
        max-width: none;
        min-height: 48px;
        font-size: var(--app-font-compact);
    }
    .runtime-form > label.span-6,
    .runtime-form > label.span-4 {
        grid-column: span 12;
    }
}

.android-host .runtime-form > label.span-6,
.android-host .runtime-form > label.span-4 {
    grid-column: span 12;
}
.android-host .runtime-form > label.is-inline-field {
    grid-template-columns: minmax(0, 1fr);
    align-items: stretch;
    row-gap: 8px;
}
.android-host .runtime-form > label.is-inline-field > small,
.android-host .runtime-form > label.is-inline-field > .terminal-actions {
    grid-column: 1;
}
.android-host .runtime-form :deep(input:not([type='checkbox'])),
.android-host .runtime-form :deep(select),
.android-host .runtime-form :deep(textarea),
.android-host .runtime-form :deep(button) {
    min-height: var(--app-control-android-touch);
}

@media (pointer: coarse) {
    .runtime-form > label.span-6,
    .runtime-form > label.span-4 {
        grid-column: span 12;
    }
    .runtime-form > label.is-inline-field {
        grid-template-columns: minmax(0, 1fr);
        align-items: stretch;
        row-gap: 8px;
    }
    .runtime-form > label.is-inline-field > small,
    .runtime-form > label.is-inline-field > .terminal-actions {
        grid-column: 1;
    }
    .terminal-actions button,
    .terminal-actions summary,
    .primary,
    .secondary,
    .danger {
        min-height: var(--app-control-android-touch);
    }
    .runtime-form :deep(input:not([type='checkbox'])),
    .runtime-form :deep(select),
    .runtime-form :deep(textarea),
    .runtime-form :deep(button) {
        min-height: var(--app-control-android-touch);
    }
}

@media (max-width: 760px) {
    .android-host {
        padding-right: env(safe-area-inset-right);
        padding-left: env(safe-area-inset-left);
    }
    .android-host .layout > nav button,
    .android-host .mobile-context select,
    .android-host .mobile-context button,
    .android-host .terminal-actions button,
    .android-host .terminal-actions summary,
    .android-host .profile-actions button,
    .android-host .tool-heading button,
    .android-host .result-actions button,
    .android-host .result-actions a,
    .android-host .primary,
    .android-host .secondary,
    .android-host .danger {
        min-height: var(--app-control-android-touch);
    }
    .android-host .runtime-form input:not([type='checkbox']),
    .android-host .runtime-form select,
    .android-host .runtime-panel select,
    .android-host .mobile-context select {
        min-height: var(--app-control-android-touch);
        font-size: var(--app-font-mobile-input);
    }
}
</style>
