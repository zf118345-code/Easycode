import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const captureApi = vi.hoisted(() => ({
    registerSession: vi.fn().mockResolvedValue({ ok: true }),
    unregisterSession: vi.fn().mockResolvedValue({ ok: true }),
    trigger: vi.fn().mockResolvedValue({ ok: true }),
    prewarm: vi.fn().mockResolvedValue({ ok: true }),
    acknowledgeAction: vi.fn().mockResolvedValue({ ok: true }),
}))
const vnextApi = vi.hoisted(() => ({
    controlCaptureMode: vi.fn().mockResolvedValue({ ok: true }),
    resolveControlCapture: vi.fn().mockResolvedValue({
        candidates: [{
            label: '按钮', role: 'button', frame_rect: [10, 20, 80, 30],
            selector: {
                'control_selector.field.provider': 'windows_uia',
                'control_selector.field.target_id': 'target',
            },
        }],
    }),
    resolveWindowCapture: vi.fn().mockResolvedValue({
        ok: true,
        title: '超能世界',
        application: 'WeChatAppEx.exe',
        window_rect: [465, 0, 915, 840],
        binding: {
            binding_version: 1, binding_id: 'window_binding_right', title: '超能世界',
            class_name: 'Chrome_WidgetWin_1', executable_name: 'WeChatAppEx.exe',
            hwnd: 202, process_id: 1002, process_started_at_ms: 1000, captured_at: '2026-09-08T12:00:00+0800',
        },
    }),
}))

vi.mock('@/api/captureApi', () => ({ captureApi }))
vi.mock('../api', () => ({ vnextApi }))

import { vnextCaptureSession } from '../captureSession'

class FakeEventSource {
    static instances: FakeEventSource[] = []
    onmessage: ((event: MessageEvent) => void) | null = null
    close = vi.fn()
    constructor() { FakeEventSource.instances.push(this) }
}

describe('VNextCaptureSession', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        FakeEventSource.instances = []
        vi.stubGlobal('EventSource', FakeEventSource)
    })
    afterEach(async () => {
        await vnextCaptureSession.disconnect()
        vi.unstubAllGlobals()
    })

    it('每种截图参数都携带明确 vNext 会话，不依赖最近聚焦的旧 IDE', async () => {
        const workspace = { workspace_id: 'w', generation: 3, project_id: 'p', project_name: '演示', project_path: 'D:/Demo', read_only: false }
        const target = { target_id: 'target', name: '窗口', type: 'windows' as const, window_title: '测试', window_match: 'contains' as const, device_serial: '', work_area: { mode: 'client' as const }, allow_physical_fallback: true }
        await vnextCaptureSession.connect(workspace, target, 'idle', vi.fn())

        const kinds = ['point', 'region', 'image', 'path'] as const
        for (const [index, capture_kind] of kinds.entries()) {
            await vnextCaptureSession.capture({ id: 'test', capture_kind }, vi.fn(), { category: 'image' })
            if (index < kinds.length - 1) {
                await vnextCaptureSession.disconnect()
                await vnextCaptureSession.connect(workspace, target, 'idle', vi.fn())
            }
        }

        expect(captureApi.trigger).toHaveBeenCalledTimes(4)
        for (const [payload] of captureApi.trigger.mock.calls) {
            expect(payload.session_id).toMatch(/^vnext_/)
            expect(payload.field_capture.request_id).toMatch(/^vnext_field_/)
        }
        expect(captureApi.registerSession).toHaveBeenCalledWith(expect.objectContaining({
            workspace_kind: 'vnext', workspace_id: 'w', workspace_generation: 3,
            capture_context: expect.objectContaining({ target_id: 'target' }),
        }))
    })

    it('运行与暂停期间在客户端直接阻止捕获', async () => {
        const workspace = { workspace_id: 'w', generation: 3, project_id: 'p', project_name: '演示', project_path: 'D:/Demo', read_only: false }
        const target = { target_id: 'target', name: '窗口', type: 'windows' as const, window_title: '测试', window_match: 'contains' as const, device_serial: '', work_area: { mode: 'client' as const }, allow_physical_fallback: true }
        await vnextCaptureSession.connect(workspace, target, 'running', vi.fn())
        await expect(vnextCaptureSession.capture({ id: 'pick', capture_kind: 'point' }, vi.fn())).rejects.toThrow('请先停止当前任务')
        expect(captureApi.trigger).not.toHaveBeenCalled()
    })

    it('工作区与目标未变化时点击捕获不重复等待会话注册', async () => {
        const workspace = { workspace_id: 'w', generation: 3, project_id: 'p', project_name: '演示', project_path: 'D:/Demo', read_only: false }
        const target = { target_id: 'target', name: '窗口', type: 'windows' as const, window_title: '测试', window_match: 'contains' as const, device_serial: '', work_area: { mode: 'client' as const }, allow_physical_fallback: true }
        await vnextCaptureSession.connect(workspace, target, 'idle', vi.fn())

        expect(captureApi.registerSession).toHaveBeenCalledTimes(1)
        await vnextCaptureSession.capture({ id: 'pick', capture_kind: 'point' }, vi.fn())

        expect(captureApi.registerSession).toHaveBeenCalledTimes(1)
        expect(captureApi.trigger).toHaveBeenCalledTimes(1)
    })

    it('独立视觉录入复用字段捕获和同一保存管理器，并只把当前分类作为默认值', async () => {
        const workspace = { workspace_id: 'w', generation: 3, project_id: 'p', project_name: '演示', project_path: 'D:/Demo', read_only: false }
        const target = { target_id: 'target', name: '窗口', type: 'windows' as const, window_title: '测试', window_match: 'contains' as const, device_serial: '', work_area: { mode: 'client' as const }, allow_physical_fallback: true }
        await vnextCaptureSession.connect(workspace, target, 'idle', vi.fn())

        await vnextCaptureSession.captureResource('ocr', vi.fn(), { title: '视觉录入 · OCR' })

        expect(captureApi.trigger).toHaveBeenCalledWith({
            session_id: expect.stringMatching(/^vnext_/),
            field_capture: expect.objectContaining({
                selection_mode: 'asset', category: 'ocr', destination: 'resource', max_rects: 1, title: '视觉录入 · OCR',
            }),
        })
    })

    it('同一时刻只允许一个参数捕获，并把宿主取消返回给原调用方', async () => {
        const workspace = { workspace_id: 'w', generation: 3, project_id: 'p', project_name: '演示', project_path: 'D:/Demo', read_only: false }
        const target = { target_id: 'target', name: '窗口', type: 'windows' as const, window_title: '测试', window_match: 'contains' as const, device_serial: '', work_area: { mode: 'client' as const }, allow_physical_fallback: true }
        const onCancel = vi.fn()
        await vnextCaptureSession.connect(workspace, target, 'idle', vi.fn())
        await vnextCaptureSession.capture({ id: 'pick', capture_kind: 'point' }, vi.fn(), { onCancel })

        await expect(vnextCaptureSession.capture({ id: 'second', capture_kind: 'region' }, vi.fn())).rejects.toThrow('请先完成或取消')
        const fieldRequestId = captureApi.trigger.mock.calls[0][0].field_capture.request_id
        const source = FakeEventSource.instances[0]
        await source.onmessage?.(new MessageEvent('message', { data: JSON.stringify({
            event: 'capture-command', kind: 'field_cancel', field_request_id: fieldRequestId,
            request_id: 'host_action_cancel', session_id: 'ignored',
        }) }))

        expect(onCancel).toHaveBeenCalledTimes(1)
        expect(captureApi.acknowledgeAction).toHaveBeenCalledWith('host_action_cancel', { ok: true })
        await expect(vnextCaptureSession.capture({ id: 'third', capture_kind: 'point' }, vi.fn())).resolves.toBeUndefined()
    })

    it('Windows 与 ADB 控件共用冻结帧语义点选、父链候选和选择器确认协议', async () => {
        const workspace = { workspace_id: 'w', generation: 3, project_id: 'p', project_name: '演示', project_path: 'D:/Demo', read_only: false }
        const target = { target_id: 'target', name: '窗口', type: 'windows' as const, window_title: '测试', window_match: 'contains' as const, device_serial: '', work_area: { mode: 'client' as const }, allow_physical_fallback: true }
        const handler = vi.fn().mockResolvedValue({ saved: true })
        await vnextCaptureSession.connect(workspace, target, 'idle', vi.fn())
        await vnextCaptureSession.capture({ id: 'capture-control', capture_kind: 'control' }, handler)

        expect(captureApi.trigger).toHaveBeenCalledWith(expect.objectContaining({
            field_capture: expect.objectContaining({ selection_mode: 'control' }),
        }))
        expect(vnextApi.controlCaptureMode).not.toHaveBeenCalled()
        const requestId = captureApi.trigger.mock.calls[0][0].field_capture.request_id
        const source = FakeEventSource.instances[0]
        await source.onmessage?.(new MessageEvent('message', { data: JSON.stringify({
            event: 'capture-command', kind: 'field_control_probe', field_request_id: requestId,
            request_id: 'probe', point: [20, 30], reference_size: [800, 600],
        }) }))
        expect(vnextApi.resolveControlCapture).toHaveBeenCalledWith(workspace, 'target', [20, 30], [800, 600])
        expect(captureApi.acknowledgeAction).toHaveBeenCalledWith('probe', expect.objectContaining({
            ok: true, candidates: expect.any(Array),
        }))

        const selector = {
            'control_selector.field.provider': 'windows_uia',
            'control_selector.field.target_id': 'target',
        }
        await source.onmessage?.(new MessageEvent('message', { data: JSON.stringify({
            event: 'capture-command', kind: 'field_confirm', field_request_id: requestId,
            request_id: 'confirm', selector,
        }) }))
        expect(handler).toHaveBeenCalledWith(expect.objectContaining({ selector }))
        expect(captureApi.acknowledgeAction).toHaveBeenCalledWith('confirm', { ok: true, saved: true })
    })

    it('窗口捕获临时切换到桌面冻结帧，并把点选结果解析为具体窗口实例', async () => {
        const workspace = { workspace_id: 'w', generation: 3, project_id: 'p', project_name: '演示', project_path: 'D:/Demo', read_only: false }
        const target = { target_id: 'target', name: '窗口', type: 'windows' as const, window_title: '测试', window_match: 'contains' as const, work_area: { mode: 'client' as const }, allow_physical_fallback: true }
        const handler = vi.fn()
        await vnextCaptureSession.connect(workspace, target, 'idle', vi.fn())

        await vnextCaptureSession.captureWindow(handler)

        expect(captureApi.registerSession).toHaveBeenLastCalledWith(expect.objectContaining({
            capture_context: expect.objectContaining({ purpose: 'window_binding' }),
        }))
        expect(captureApi.trigger).toHaveBeenCalledWith(expect.objectContaining({
            field_capture: expect.objectContaining({ selection_mode: 'point', title: '捕获目标窗口' }),
        }))
        const requestId = captureApi.trigger.mock.calls[0][0].field_capture.request_id
        const source = FakeEventSource.instances[0]
        await source.onmessage?.(new MessageEvent('message', { data: JSON.stringify({
            event: 'capture-command', kind: 'field_confirm', field_request_id: requestId,
            request_id: 'window-confirm', snapshot_id: 'snapshot-desktop', point: [700, 200], reference_size: [1920, 1080],
        }) }))

        expect(vnextApi.resolveWindowCapture).toHaveBeenCalledWith(
            workspace, expect.stringMatching(/^vnext_/), 'snapshot-desktop', [700, 200], [1920, 1080],
        )
        expect(handler).toHaveBeenCalledWith(expect.objectContaining({
            binding: expect.objectContaining({ hwnd: 202 }),
        }))
        expect(captureApi.acknowledgeAction).toHaveBeenCalledWith('window-confirm', { ok: true })
        expect(captureApi.registerSession).toHaveBeenLastCalledWith(expect.objectContaining({
            capture_context: expect.not.objectContaining({ purpose: 'window_binding' }),
        }))
    })
})
