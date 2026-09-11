import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const replay = vi.hoisted(() => ({
    sessions: vi.fn(), session: vi.fn(), timeline: vi.fn(), frames: vi.fn(),
    status: vi.fn(), start: vi.fn(), stop: vi.fn(), mark: vi.fn(),
    frameBlob: vi.fn(), verify: vi.fn(), catalog: vi.fn(),
    analyzeFrame: vi.fn(), analyzeSession: vi.fn(), reports: vi.fn(),
    deleteReport: vi.fn(), compare: vi.fn(), comparisonBlob: vi.fn(),
    createExport: vi.fn(), exportBlob: vi.fn(), deleteSession: vi.fn(),
}))

vi.mock('../replayApi', () => ({ replayApi: replay }))

import VNextReplayWorkspace from '../components/VNextReplayWorkspace.vue'
import replayWorkspaceSource from '../components/VNextReplayWorkspace.vue?raw'
import { useVNextStore } from '../store'

const workspace = {
    workspace_id: 'workspace-replay', generation: 1, project_id: 'project-replay',
    project_name: '回放项目', project_path: 'D:/Replay', read_only: false,
}
const frame = {
    kind: 'frame' as const, frame_id: 'frame_1', sequence: 1, capture_sequence: 1,
    captured_at: '2026-09-01T00:00:00Z', timestamp_ns: 1,
    width: 1280, height: 720, orientation: 'landscape', dpi: 96,
    target_id: 'target_1', target_kind: 'windows', target_title: '游戏窗口',
    recording_segment_id: 'segment_1', space_version: 'target_1:1280x720',
    screen_region: [0, 0, 1280, 720], change_score: 1, bytes: 1024,
    sha256: 'a'.repeat(64), file: 'frames/frame_1.png', sort_sequence: 1,
}
const summary = {
    session_id: 'session_1', recording_format: 3, project_name: '回放项目',
    started_at: '2026-09-01T00:00:00Z', stopped_at: '2026-09-01T00:01:00Z',
    status: 'completed', terminal_reason: 'completed', strategy: 'changed_frames',
    target_id: 'target_1', target_kind: 'windows', target_title: '游戏窗口',
    frame_count: 1, capture_count: 3, segment_count: 1, marker_count: 1,
    drop_event_count: 1, dropped_frame_count: 0, policy_skipped_frame_count: 2,
    total_bytes: 1024, locked: false, final: true, recovered: false,
    integrity: 'unchecked', issue_count: 0,
}

function installComponentStyles(source: string) {
    const style = document.createElement('style')
    style.dataset.replayLayoutTest = 'true'
    style.textContent = source.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] || ''
    document.head.append(style)
}

describe('VNextReplayWorkspace', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        vi.stubGlobal('URL', {
            ...URL,
            createObjectURL: vi.fn(() => 'blob:replay-frame'),
            revokeObjectURL: vi.fn(),
        })
        replay.sessions.mockResolvedValue([summary])
        replay.status.mockResolvedValue({
            active: false, status: 'idle', session_id: '', strategy: 'changed_frames',
            frame_count: 0, capture_count: 0, dropped_frame_count: 0,
            policy_skipped_frame_count: 0, disk_bytes: 0, elapsed_ms: 0,
            terminal_reason: '', last_error: '', target_id: '', target_title: '',
        })
        replay.session.mockResolvedValue({
            ...summary, segments: [{
                event: 'opened', recording_segment_id: 'segment_1', target_id: 'target_1',
                target_kind: 'windows', target_title: '游戏窗口', width: 1280, height: 720,
            }], markers: [{
                kind: 'user', marker_id: 'marker_1', label: '故障点', capture_sequence: 2,
                marked_at: '2026-09-01T00:00:01Z', recording_segment_id: 'segment_1',
            }], drops: [{
                kind: 'policy_filtered', drop_id: 'drop_1', reason: 'unchanged',
                start_capture_sequence: 2, end_capture_sequence: 3, count: 2,
                started_at: '2026-09-01T00:00:01Z', ended_at: '2026-09-01T00:00:02Z',
            }], terminal: { terminal_reason: 'completed' }, issues: [],
        })
        replay.timeline.mockResolvedValue({
            total: 3, offset: 0, limit: 300,
            items: [frame, {
                kind: 'marker', marker_id: 'marker_1', label: '故障点', capture_sequence: 2,
                marked_at: '2026-09-01T00:00:01Z', sort_sequence: 2,
            }, {
                kind: 'drop', drop_id: 'drop_1', reason: 'unchanged',
                start_capture_sequence: 2, end_capture_sequence: 3, count: 2,
                started_at: '2026-09-01T00:00:01Z', ended_at: '2026-09-01T00:00:02Z',
                sort_sequence: 3,
            }], issues: [],
        })
        replay.frames.mockResolvedValue({ total: 1, offset: 0, limit: 200, frames: [frame], issues: [] })
        replay.frameBlob.mockResolvedValue(new Blob(['frame'], { type: 'image/png' }))
        replay.reports.mockResolvedValue([])
        replay.catalog.mockResolvedValue({
            available: true, unavailable_reason: '', diagnostics: [], analyses: [{
                analysis_id: 'project.main:statement_find', function_id: 'official.image.find',
                owner_function_id: 'project.main', statement_id: 'statement_find',
                display_name: '图像.查找', side_effect_free: true,
                implementation: 'official_dedicated_adapter',
            }],
        })
        replay.verify.mockResolvedValue({
            session_id: 'session_1', ok: true, integrity: 'verified',
            verified_frame_count: 1, frame_count: 1, issues: [],
        })
        replay.analyzeFrame.mockResolvedValue({ analysis_run_id: 'analysis_1' })
        replay.start.mockResolvedValue({ active: true, status: 'recording' })
    })
    afterEach(() => {
        vi.unstubAllGlobals()
        document.querySelectorAll('[data-replay-layout-test]').forEach((element) => element.remove())
    })

    function setup(attachToDocument = false) {
        const store = useVNextStore()
        store.workspace = workspace
        store.targets = [{
            target_id: 'target_1', name: '游戏窗口', type: 'windows', window_title: 'Game',
            window_match: 'contains', work_area: { mode: 'client' }, allow_physical_fallback: true,
        }]
        store.defaultTargetId = 'target_1'
        return mount(VNextReplayWorkspace, attachToDocument ? { attachTo: document.body } : undefined)
    }

    it('用会话、虚拟时间线和原帧检查器形成三栏真实闭环', async () => {
        const wrapper = setup()
        await flushPromises()
        await flushPromises()

        expect(wrapper.get('.replay-sessions').text()).toContain('游戏窗口')
        expect(wrapper.get('.frame-stage img').attributes('src')).toBe('blob:replay-frame')
        expect(wrapper.findAll('.timeline-row')).toHaveLength(3)
        expect(wrapper.get('.metadata-list').text()).toContain('1280 × 720')
        expect(wrapper.text()).toContain('只重新执行图像与文字识别，不会产生点击、文件或网络操作')
        expect(wrapper.get('.technical-frame-details').attributes('open')).toBeUndefined()

        await wrapper.findAll('.viewer-actions button')[0].trigger('click')
        expect(wrapper.emitted('open-history-frame')).toEqual([['session_1', 1]])
        await wrapper.findAll('.viewer-actions button')[1].trigger('click')
        await flushPromises()
        expect(wrapper.get('.verification-result').text()).toContain('完整性校验通过')

        await wrapper.get('.analysis-list input').setValue(true)
        await wrapper.findAll('.inline-actions button')[0].trigger('click')
        await flushPromises()
        expect(replay.analyzeFrame).toHaveBeenCalledWith(
            workspace, 'session_1', 1, ['project.main:statement_find'],
        )
        expect(wrapper.get('.analysis-result').text()).toContain('analysis_1')
        wrapper.unmount()
    })

    it('开始录制只提交 Windows/ADB 目标与有界默认策略', async () => {
        const wrapper = setup()
        await flushPromises()
        await wrapper.get('.primary-action').trigger('click')
        await flushPromises()

        expect(replay.start).toHaveBeenCalledWith(workspace, expect.objectContaining({
            target_id: 'target_1', recording_mode: 'changed_frames', target_fps: 15,
            queue_capacity: 48, max_duration_ms: 1_800_000,
            max_session_bytes: 2_147_483_648, min_free_bytes: 536_870_912,
        }))
        wrapper.unmount()
    })

    it('像素比较沿用紧凑同行字段，极窄视口只重排字段而不拆散标签与 Control', async () => {
        installComponentStyles(replayWorkspaceSource)
        const wrapper = setup(true)
        await flushPromises()
        await flushPromises()

        const fields = wrapper.findAll('.compare-inputs label')
        expect(fields).toHaveLength(2)
        expect(fields.every((field) => getComputedStyle(field.element).display === 'grid')).toBe(true)
        expect(fields.every((field) => getComputedStyle(field.element).gridTemplateColumns.includes('34px'))).toBe(true)
        expect(getComputedStyle(fields[0].get('input').element).height).toBe('var(--app-control-default)')
        expect(getComputedStyle(wrapper.get('.compact-field select').element).height).toBe('var(--app-control-default)')
        expect(getComputedStyle(wrapper.get('.advanced-options input').element).height).toBe('var(--app-control-default)')
        expect(getComputedStyle(wrapper.get('.primary-action').element).minHeight).toBe('var(--app-control-default)')
        expect(replayWorkspaceSource).toContain('@media (max-width: 420px) { .compare-inputs { grid-template-columns: 1fr; } }')
        wrapper.unmount()
    })

    it('主流程未通过检查时保留回放功能并明确说明分析不可用', async () => {
        replay.catalog.mockResolvedValue({
            available: false,
            unavailable_reason: '当前项目尚未通过检查：必填值尚未配置',
            diagnostics: [{ severity: 'error', message: '必填值尚未配置' }],
            analyses: [],
        })
        const wrapper = setup()
        await flushPromises()
        await flushPromises()

        expect(wrapper.find('.frame-stage img').exists()).toBe(true)
        expect(wrapper.get('.analysis-unavailable').text()).toContain('必填值尚未配置')
        expect(wrapper.findAll('.inline-actions button').every(button => button.attributes('disabled') !== undefined)).toBe(true)
        wrapper.unmount()
    })

    it('窄屏会话与检查器抽屉圈定焦点并在退出后返回触发按钮', async () => {
        const wrapper = setup(true)
        await flushPromises()
        await flushPromises()

        const sessionsTrigger = wrapper.get('.sessions-toggle')
        ;(sessionsTrigger.element as HTMLElement).focus()
        await sessionsTrigger.trigger('click')
        await flushPromises()
        expect(wrapper.get('.replay-sessions').attributes('role')).toBe('dialog')
        expect(document.activeElement).toBe(wrapper.get('.sessions-close').element)
        await wrapper.get('.replay-sessions').trigger('keydown', { key: 'Escape' })
        await flushPromises()
        expect(document.activeElement).toBe(sessionsTrigger.element)

        const inspectorTrigger = wrapper.get('.inspector-toggle')
        ;(inspectorTrigger.element as HTMLElement).focus()
        await inspectorTrigger.trigger('click')
        await flushPromises()
        expect(wrapper.get('.replay-inspector').attributes('role')).toBe('dialog')
        expect(document.activeElement).toBe(wrapper.get('.inspector-close').element)
        await wrapper.get('.replay-inspector').trigger('keydown', { key: 'Escape' })
        await flushPromises()
        expect(document.activeElement).toBe(inspectorTrigger.element)
        wrapper.unmount()
    })
})
