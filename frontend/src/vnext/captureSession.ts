import { captureApi } from '@/api/captureApi'
import type { AssetCategoryId, ParameterUiAction, TargetDefinition, WorkspaceIdentity } from './types'
import { vnextApi } from './api'

type CaptureResult = Record<string, unknown>
type CaptureHandler = (payload: CaptureResult) => Promise<Record<string, unknown> | void> | Record<string, unknown> | void
interface CaptureRegistration {
    handler: CaptureHandler
    targetId: string
    targetType: string
    selectionMode: string
    onCancel?: () => void | Promise<void>
    onError?: (message: string) => void | Promise<void>
}
interface CaptureOptions {
    category?: AssetCategoryId
    destination?: 'parameter' | 'resource'
    maxRects?: number
    title?: string
    onCancel?: CaptureRegistration['onCancel']
    onError?: CaptureRegistration['onError']
}

class VNextCaptureSession {
    private sessionId = sessionStorage.getItem('easycodeVNextCaptureSession') || `vnext_${crypto.randomUUID().replaceAll('-', '')}`
    private workspace: WorkspaceIdentity | null = null
    private target: TargetDefinition | null = null
    private executionState = 'idle'
    private eventSource: EventSource | null = null
    private heartbeat: ReturnType<typeof setInterval> | null = null
    private handlers = new Map<string, CaptureRegistration>()
    private onError: (message: string) => void = () => undefined
    private lastRegistrationKey = ''
    private lastRegisteredAt = 0
    private registrationPromise: Promise<void> | null = null
    private registrationPromiseKey = ''
    private prewarmStarted = false
    private capturePurpose = ''

    constructor() { sessionStorage.setItem('easycodeVNextCaptureSession', this.sessionId) }

    async connect(workspace: WorkspaceIdentity, target: TargetDefinition | null, executionState: string, onError: (message: string) => void) {
        this.workspace = workspace
        this.target = target
        this.executionState = executionState
        this.onError = onError
        await this.register(true)
        if (!this.eventSource) {
            this.eventSource = new EventSource('/api/ui-control/events')
            this.eventSource.onmessage = event => this.receive(event)
        }
        if (!this.heartbeat) this.heartbeat = setInterval(() => this.register(false).catch(() => undefined), 25_000)
        if (!this.prewarmStarted) {
            this.prewarmStarted = true
            captureApi.prewarm().catch(() => { this.prewarmStarted = false })
        }
    }

    update(target: TargetDefinition | null, executionState: string) {
        this.target = target
        this.executionState = executionState
        this.register(false).catch(() => undefined)
    }

    async openRecordingFrame(recordingSessionId: string, frameIndex: number) {
        if (!this.workspace) throw new Error('请先打开项目')
        if (['queued', 'running', 'paused'].includes(this.executionState)) throw new Error('请先停止当前任务')
        await this.register(true)
        return captureApi.replay(recordingSessionId, frameIndex, this.sessionId)
    }

    async register(focused: boolean) {
        if (!this.workspace) return
        const key = this.registrationKey()
        if (this.registrationPromise && this.registrationPromiseKey === key) {
            await this.registrationPromise
            return
        }
        const payload = {
            session_id: this.sessionId,
            workspace_kind: 'vnext',
            project_path: this.workspace.project_path,
            workspace_id: this.workspace.workspace_id,
            workspace_generation: this.workspace.generation,
            project_name: this.workspace.project_name,
            target_name: this.target?.name || '',
            execution_state: this.executionState,
            recording_active: false,
            origin: window.location.origin,
            last_focus_at: focused ? Date.now() / 1000 : undefined,
            capture_context: {
                workspace_kind: 'vnext',
                target_id: this.target?.target_id || '',
                platform: this.target?.type || '',
                ...(this.capturePurpose ? { purpose: this.capturePurpose } : {}),
            },
        }
        const pending = captureApi.registerSession(payload).then(() => {
            this.lastRegistrationKey = key
            this.lastRegisteredAt = Date.now()
        }).finally(() => {
            if (this.registrationPromise === pending) {
                this.registrationPromise = null
                this.registrationPromiseKey = ''
            }
        })
        this.registrationPromise = pending
        this.registrationPromiseKey = key
        await pending
    }

    private registrationKey() {
        if (!this.workspace) return ''
        return [
            this.workspace.workspace_id,
            this.workspace.generation,
            this.target?.target_id || '',
            this.target?.type || '',
            this.executionState,
            this.capturePurpose,
        ].join(':')
    }

    private async ensureCaptureRegistration() {
        const fresh = this.lastRegistrationKey === this.registrationKey()
            && Date.now() - this.lastRegisteredAt < 60_000
        if (!fresh) await this.register(true)
    }

    async capture(action: ParameterUiAction, handler: CaptureHandler, options: CaptureOptions = {}) {
        if (!this.workspace) throw new Error('请先打开项目')
        if (['queued', 'running', 'paused'].includes(this.executionState)) throw new Error('请先停止当前任务')
        if (!this.target) throw new Error('请先配置运行目标')
        if (this.handlers.size) throw new Error('请先完成或取消当前参数捕获')
        const selectionMode = action.capture_kind === 'image' ? 'asset' : action.capture_kind
        const requestId = `vnext_field_${crypto.randomUUID().replaceAll('-', '')}`
        this.handlers.set(requestId, {
            handler,
            targetId: this.target.target_id,
            targetType: this.target.type,
            selectionMode: selectionMode || '',
            onCancel: options.onCancel,
            onError: options.onError,
        })
        // connect/update already publish the complete target context. Avoid a
        // redundant HTTP round trip on the common click-to-capture path while
        // still repairing stale or changed sessions before capture.
        try { await this.ensureCaptureRegistration() }
        catch (error) {
            this.handlers.delete(requestId)
            throw error
        }
        const hostSelectionMode = selectionMode
        if (!['point', 'region', 'asset', 'color', 'path', 'control'].includes(hostSelectionMode || '')) {
            this.handlers.delete(requestId)
            throw new Error(this.target.type === 'android_local'
                ? 'Android 本机控件请在 APK Player 的字段动作中捕获'
                : '当前捕获宿主尚不支持该采集类型')
        }
        try {
            await captureApi.trigger({ session_id: this.sessionId, field_capture: {
                request_id: requestId,
                selection_mode: hostSelectionMode,
                category: options.category || 'image',
                destination: options.destination || 'parameter',
                max_rects: Math.max(1, options.maxRects || 1),
                title: options.title || '设置函数参数',
            } })
        } catch (error) {
            this.handlers.delete(requestId)
            throw error
        }
    }

    async captureResource(category: AssetCategoryId, handler: CaptureHandler, options: Omit<CaptureOptions, 'category'> = {}) {
        return this.capture(
            { id: 'capture-resource', capture_kind: 'image' },
            handler,
            { ...options, category, destination: 'resource', title: options.title || '视觉录入资源' },
        )
    }

    async captureWindow(handler: CaptureHandler, options: Pick<CaptureOptions, 'onCancel' | 'onError'> = {}) {
        if (!this.workspace) throw new Error('请先打开项目')
        if (['queued', 'running', 'paused'].includes(this.executionState)) throw new Error('请先停止当前任务')
        if (this.handlers.size) throw new Error('请先完成或取消当前参数捕获')
        const requestId = `vnext_window_${crypto.randomUUID().replaceAll('-', '')}`
        this.capturePurpose = 'window_binding'
        this.handlers.set(requestId, {
            handler,
            targetId: '',
            targetType: 'windows',
            selectionMode: 'window',
            onCancel: options.onCancel,
            onError: options.onError,
        })
        try {
            await this.register(true)
            await captureApi.trigger({ session_id: this.sessionId, field_capture: {
                request_id: requestId,
                selection_mode: 'point',
                category: 'image',
                destination: 'parameter',
                max_rects: 1,
                title: '捕获目标窗口',
            } })
        } catch (error) {
            this.handlers.delete(requestId)
            await this.finishSpecialCapture()
            throw error
        }
    }

    private async finishSpecialCapture() {
        if (!this.capturePurpose) return
        this.capturePurpose = ''
        await this.register(true).catch(() => undefined)
    }

    private async receive(event: MessageEvent) {
        let data: Record<string, unknown>
        try { data = JSON.parse(String(event.data || '{}')) }
        catch { return }
        if (data.event === 'screenshot-error' && (!data.session_id || data.session_id === this.sessionId)) {
            const message = String(data.message || '截图捕获失败')
            const pending = [...this.handlers.values()]
            this.handlers.clear()
            await this.finishSpecialCapture()
            for (const registration of pending) await registration.onError?.(message)
            this.onError(message)
            return
        }
        if (data.event !== 'capture-command') return
        const fieldRequestId = String(data.field_request_id || '')
        const registration = this.handlers.get(fieldRequestId)
        if (!registration && data.session_id !== this.sessionId) return
        let result: Record<string, unknown> = { ok: false, message: '捕获请求已经失效' }
        try {
            if (String(data.kind || '') === 'field_cancel') {
                this.handlers.delete(fieldRequestId)
                if (registration?.selectionMode === 'window') await this.finishSpecialCapture()
                await registration?.onCancel?.()
                result = { ok: true }
            } else if (String(data.kind || '') === 'field_control_probe' && registration) {
                const rawPoint = data.point
                const rawSize = data.reference_size
                if (!Array.isArray(rawPoint) || rawPoint.length !== 2) throw new Error('控件捕获没有返回有效坐标')
                if (!Array.isArray(rawSize) || rawSize.length !== 2) throw new Error('控件捕获缺少冻结帧尺寸')
                const point: [number, number] = [Number(rawPoint[0]), Number(rawPoint[1])]
                const referenceSize: [number, number] = [Number(rawSize[0]), Number(rawSize[1])]
                if (!point.every(Number.isFinite) || !referenceSize.every(value => Number.isFinite(value) && value > 0)) {
                    throw new Error('控件捕获坐标空间无效')
                }
                const resolved = await vnextApi.resolveControlCapture(
                    this.workspace!, registration.targetId, point, referenceSize,
                )
                result = { ok: true, candidates: resolved.candidates }
            } else if (String(data.kind || '') === 'field_confirm' && registration) {
                this.handlers.delete(fieldRequestId)
                if (registration.selectionMode === 'window') {
                    const rawPoint = data.point
                    const rawSize = data.reference_size
                    const snapshotId = String(data.snapshot_id || '')
                    if (!Array.isArray(rawPoint) || rawPoint.length !== 2 || !snapshotId) throw new Error('窗口捕获没有返回有效位置')
                    if (!Array.isArray(rawSize) || rawSize.length !== 2) throw new Error('窗口捕获缺少冻结帧尺寸')
                    const point: [number, number] = [Number(rawPoint[0]), Number(rawPoint[1])]
                    const referenceSize: [number, number] = [Number(rawSize[0]), Number(rawSize[1])]
                    if (!point.every(Number.isFinite) || !referenceSize.every(value => Number.isFinite(value) && value > 0)) throw new Error('窗口捕获坐标空间无效')
                    const resolved = await vnextApi.resolveWindowCapture(
                        this.workspace!, this.sessionId, snapshotId, point, referenceSize,
                    )
                    await this.finishSpecialCapture()
                    result = { ok: true, ...(await registration.handler(resolved) || {}) }
                    await captureApi.acknowledgeAction(String(data.request_id || ''), result).catch(() => undefined)
                    return
                }
                if (registration.selectionMode === 'control') {
                    if (registration.targetType === 'android_local') throw new Error('Android 本机控件应由 APK Player 回填')
                    const selector = data.selector
                    if (!selector || typeof selector !== 'object') throw new Error('控件捕获没有返回有效选择器')
                    const selectorTarget = String((selector as Record<string, unknown>)['control_selector.field.target_id'] || '')
                    if (selectorTarget && selectorTarget !== registration.targetId) throw new Error('控件选择器不属于当前语句目标')
                }
                result = { ok: true, ...(await registration.handler(data) || {}) }
            }
        } catch (error) {
            if (registration?.selectionMode === 'window') await this.finishSpecialCapture()
            result = { ok: false, message: error instanceof Error ? error.message : String(error) }
        }
        await captureApi.acknowledgeAction(String(data.request_id || ''), result).catch(() => undefined)
    }

    async disconnect() {
        if (this.heartbeat) clearInterval(this.heartbeat)
        this.heartbeat = null
        this.eventSource?.close()
        this.eventSource = null
        this.handlers.clear()
        await captureApi.unregisterSession(this.sessionId).catch(() => undefined)
        this.lastRegistrationKey = ''
        this.lastRegisteredAt = 0
        this.registrationPromise = null
        this.registrationPromiseKey = ''
        this.prewarmStarted = false
        this.capturePurpose = ''
    }
}

export const vnextCaptureSession = new VNextCaptureSession()
