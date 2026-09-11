import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
    playerRuntimeBootstrap: vi.fn(),
    playerRuntimeRun: vi.fn(),
    playerRuntimeDangerousOperations: vi.fn(),
    playerRuntimePreflight: vi.fn(),
    playerRuntimeProfiles: vi.fn(),
    savePlayerRuntimeProfile: vi.fn(),
    deletePlayerRuntimeProfile: vi.fn(),
    runStatus: vi.fn(),
    cancelRun: vi.fn(),
    pauseRun: vi.fn(),
    resumeRun: vi.fn(),
    playerRuntimeActions: vi.fn(),
    startPlayerControlCapture: vi.fn(),
    confirmPlayerControlCapture: vi.fn(),
    cancelPlayerControlCapture: vi.fn(),
    restorePlayerProfileImage: vi.fn(),
    playerRuntimeRecordingStatus: vi.fn(),
    stopPlayerRuntimeRecording: vi.fn(),
    playerRuntimeRecordingSessions: vi.fn(),
    playerRuntimeRecordingSession: vi.fn(),
    playerRuntimeRecordingFrame: vi.fn(),
    deletePlayerRuntimeRecordingSession: vi.fn(),
    createPlayerRuntimeRecordingExport: vi.fn(),
    playerRuntimeRecordingExportBlob: vi.fn(),
    acknowledgeCaptureAction: vi.fn(),
}))

vi.mock('../playerApi', () => ({
    mergeRuntimeSession: (_current: unknown, next: unknown) => next,
    vnextApi: api,
}))

import VNextPlayerApp from '../VNextPlayerApp.vue'
import playerAppSource from '../VNextPlayerApp.vue?raw'

function installComponentStyles(source: string) {
    const element = document.createElement('style')
    element.dataset.playerLayoutTest = 'true'
    element.textContent = source.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] || ''
    document.head.append(element)
}

const form = {
    schema_version: 3,
    title: '测试 Player',
    features: { recording: true },
    pages: [{ page_id: 'main', title: '运行', controls: [{
        control_id: 'count', type: 'number', label: '运行次数', help: '', default: 1,
        options: [], required: false,
        binding: { kind: 'project_variable', variable_id: 'variable-count' },
        layout: { span: 12 }, parameter_ui: { control: 'number' }, constraints: { min: 1 },
        platforms: ['windows'], source_type: 'int64', type_fingerprint: 'sha256:count',
    }] }],
}

describe('VNextPlayerApp error and session lifecycle', () => {
    const nativePostMessage = vi.fn()
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        localStorage.clear()
        delete window.EasyCodeAndroid
        api.acknowledgeCaptureAction.mockResolvedValue({ ok: true })
        api.playerRuntimeBootstrap.mockResolvedValue({
            available: true,
            form,
            targets: [],
            assets: { categories: [], assets: [] },
            default_target_id: null,
            bundle: { project_id: 'project_1', release_id: 'release_1', name: '测试包' },
        })
        api.playerRuntimeProfiles.mockResolvedValue({ profiles: [] })
        api.playerRuntimeDangerousOperations.mockResolvedValue({ operations: [] })
        api.playerRuntimeRecordingStatus.mockResolvedValue({ active: false, status: 'idle' })
        api.stopPlayerRuntimeRecording.mockResolvedValue({ active: false, status: 'stopped', terminal_reason: 'user_stopped' })
        api.playerRuntimeRecordingSessions.mockResolvedValue({ sessions: [] })
        api.playerRuntimeActions.mockResolvedValue({
            platform: null, profile_id: null, profile_revision: null,
            blocked_reason: '请先保存并选择一个配置方案', actions: [],
        })
        ;(window as any).chrome = { webview: { postMessage: nativePostMessage, addEventListener: vi.fn(), removeEventListener: vi.fn() } }
        document.querySelectorAll('[data-player-layout-test]').forEach((element) => element.remove())
    })
    afterEach(() => {
        delete (window as any).chrome
    })

    it('桌面顶部页签与参数、运行区分别滚动，移动端回到单一连续滚动', () => {
        expect(playerAppSource).toMatch(/\.layout\s*\{[\s\S]*?overflow:\s*hidden/)
        expect(playerAppSource).toMatch(/grid-template-columns:\s*minmax\(360px,\s*1fr\)\s*5px\s*var\(--runtime-panel-width,\s*320px\)/)
        expect(playerAppSource).toMatch(/\.page-tabs\s*\{\s*grid-column:\s*1;\s*grid-row:\s*1/)
        expect(playerAppSource).toMatch(/\.content\s*\{[\s\S]*?overflow-x:\s*hidden;[\s\S]*?overflow-y:\s*auto/)
        expect(playerAppSource).toMatch(/\.runtime-panel\s*\{[\s\S]*?overflow-x:\s*hidden;[\s\S]*?overflow-y:\s*auto/)
        expect(playerAppSource).toMatch(/@media\s*\(max-width:\s*760px\)[\s\S]*?\.layout,[\s\S]*?overflow:\s*auto/)
        expect(playerAppSource).toMatch(/@media\s*\(max-width:\s*760px\)[\s\S]*?\.runtime-panel\s*\{[\s\S]*?overflow:\s*visible/)
    })

    it('未发布录制能力时不展示入口且不读取本机记录', async () => {
        const compactForm = structuredClone(form)
        compactForm.features.recording = false
        api.playerRuntimeBootstrap.mockResolvedValue({
            available: true, form: compactForm, targets: [], default_target_id: null,
            assets: { categories: [], assets: [] },
            bundle: { project_id: 'project_1', release_id: 'release_1', name: '小脚本' },
        })
        const wrapper = mount(VNextPlayerApp)
        await flushPromises()

        expect(wrapper.find('.recording-settings').exists()).toBe(false)
        expect(wrapper.find('.recording-runtime').exists()).toBe(false)
        expect(api.playerRuntimeRecordingSessions).not.toHaveBeenCalled()
        wrapper.unmount()
    })

    it('桌面运行表单只让简单字段同行，Android 宿主保持单列触控语义', async () => {
        window.EasyCodeAndroid = {} as typeof window.EasyCodeAndroid
        const layoutForm: any = structuredClone(form)
        layoutForm.pages[0].controls = [{
            ...layoutForm.pages[0].controls[0],
            layout: { span: 6 },
            help: '最多运行十次',
        }, {
            control_id: 'region', type: 'region', label: '识别区域', help: '',
            default: { x: 0, y: 0, width: 10, height: 10 }, options: [], required: false,
            binding: { kind: 'project_variable', variable_id: 'variable-region' },
            layout: { span: 4 }, parameter_ui: { control: 'region' }, constraints: {},
            platforms: ['android_local'], source_type: 'rect', type_fingerprint: 'sha256:region',
        }]
        api.playerRuntimeBootstrap.mockResolvedValue({
            available: true,
            form: layoutForm,
            targets: [],
            assets: { categories: [], assets: [] },
            default_target_id: null,
            bundle: { project_id: 'project_1', release_id: 'release_1', name: '布局测试' },
        })
        installComponentStyles(playerAppSource)
        const wrapper = mount(VNextPlayerApp, { attachTo: document.body })
        await flushPromises()

        const count = wrapper.get('[data-control-id="count"]')
        const region = wrapper.get('[data-control-id="region"]')
        expect(wrapper.get('.player-app').classes()).toContain('android-host')
        expect(count.classes()).toContain('is-inline-field')
        expect(region.classes()).not.toContain('is-inline-field')
        expect(getComputedStyle(count.element).display).toBe('grid')
        expect(getComputedStyle(count.element).gridTemplateColumns.replaceAll(' ', '')).toBe('minmax(0,1fr)')
        expect(getComputedStyle(count.element).alignItems).toBe('stretch')
        expect(getComputedStyle(count.element).gridColumn).toContain('span 12')
        wrapper.unmount()
    })

    it('重新打开 Player 时直接恢复上次可用的保存方案', async () => {
        api.playerRuntimeProfiles.mockResolvedValue({
            profiles: [{
                profile_id: 'profile_saved', name: '日常方案', target_id: '',
                values: { count: 6 }, revision: 3,
            }],
        })
        const wrapper = mount(VNextPlayerApp, { attachTo: document.body })
        await flushPromises()

        expect((wrapper.findAll('.runtime-tools select')[0].element as HTMLSelectElement).value).toBe('profile_saved')
        expect((wrapper.get('input[placeholder="方案名称"]').element as HTMLInputElement).value).toBe('日常方案')
        expect((wrapper.get('input[type="number"]').element as HTMLInputElement).value).toBe('6')
        wrapper.unmount()
    })

    it('冷启动时在共享 Player 内展示宿主反馈并定位原字段', async () => {
        const scrollIntoView = vi.fn()
        Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
            configurable: true,
            value: scrollIntoView,
        })
        api.playerRuntimeBootstrap.mockResolvedValue({
            available: true,
            form,
            targets: [],
            assets: { categories: [], assets: [] },
            default_target_id: null,
            bundle: { project_id: 'project_1', release_id: 'release_1', name: '测试包' },
            host_feedback: {
                ok: false,
                message: '字段采集已取消；旧值保持不变',
                control_id: 'count',
            },
        })

        const wrapper = mount(VNextPlayerApp, { attachTo: document.body })
        await flushPromises()

        expect(wrapper.get('.player-feedback').text()).toContain('字段采集已取消')
        expect(scrollIntoView).toHaveBeenCalledWith({ block: 'center', behavior: 'smooth' })
        expect(document.activeElement).not.toBe(wrapper.get('[data-control-id="count"] input').element)
        expect(wrapper.get('[data-control-id="count"]').classes()).toContain('capture-return-highlight')
        wrapper.unmount()
    })

    it('运行失败保留 Player 表单、日志和重试入口', async () => {
        api.playerRuntimeRun.mockRejectedValue(new Error('目标不支持后台输入'))
        const wrapper = mount(VNextPlayerApp)
        await flushPromises()

        await wrapper.get('.primary').trigger('click')
        await flushPromises()

        expect(wrapper.find('.layout').exists()).toBe(true)
        expect(wrapper.get('.layout').classes()).toContain('without-nav')
        expect(wrapper.get('.runtime-error').text()).toContain('目标不支持后台输入')
        expect(wrapper.text()).not.toContain('Player 无法启动')
        expect(wrapper.get('.primary').text()).toContain('运行主程序')
        wrapper.unmount()
    })

    it('实例服务连续失联时保留现场并指向控制台诊断而不是冒充脚本失败', async () => {
        vi.useFakeTimers()
        try {
            api.playerRuntimeRun.mockResolvedValue({ execution_id: 'run_lost', status: 'running', events: [] })
            api.runStatus.mockRejectedValue(Object.assign(new Error('无法连接 Player 服务。'), { status: 503 }))
            const wrapper = mount(VNextPlayerApp)
            await flushPromises()

            void wrapper.get('.primary').trigger('click')
            await flushPromises()
            await vi.advanceTimersByTimeAsync(1_500)
            await flushPromises()

            expect(api.runStatus).toHaveBeenCalledTimes(3)
            expect(wrapper.get('.runtime-error').text()).toContain('本次运行结果未知')
            expect(wrapper.get('.runtime-error').text()).toContain('导出最近诊断包')
            expect(wrapper.find('.actions .danger').exists()).toBe(false)
            wrapper.unmount()
        } finally {
            vi.useRealTimers()
        }
    })

    it('活动脚本关闭前确认，确认后停止运行并授权原生宿主退出', async () => {
        api.playerRuntimeRun.mockResolvedValue({
            execution_id: 'run_close', status: 'running', events: [], event_cursor: 0,
        })
        api.cancelRun.mockResolvedValue({
            execution_id: 'run_close', status: 'cancelled', events: [], event_cursor: 0,
        })
        const wrapper = mount(VNextPlayerApp, { attachTo: document.body })
        await flushPromises()
        ;(wrapper.get('.actions .primary').element as HTMLButtonElement).click()
        await flushPromises()

        await wrapper.get('[aria-label="关闭窗口"]').trigger('click')
        await flushPromises()
        expect(document.body.textContent).toContain('当前脚本仍在运行')
        ;(document.querySelector('[role="alertdialog"] .vnext-button.is-solid') as HTMLButtonElement).click()
        await flushPromises()

        expect(api.cancelRun).toHaveBeenCalledWith('run_close')
        expect(nativePostMessage).toHaveBeenCalledWith({ event: 'window-command', version: 1, command: 'close-confirmed' })
        wrapper.unmount()
    })

    it('递归删除在每次运行前展示实际授权目录并只提交确认身份', async () => {
        api.playerRuntimeDangerousOperations.mockResolvedValue({
            operations: [{
                confirmation_id: 'sha256:confirm', statement_id: 'statement.delete',
                function_id: 'official.directory.delete_tree', display_name: '递归删除目录',
                display_path: 'D:\\Sandbox\\cache', authorization_root_id: 'root.cache',
                execution_config_revision: 'sha256:config', contract_fingerprint: 'sha256:contract',
            }],
        })
        api.playerRuntimeRun.mockResolvedValue({ execution_id: 'run_delete', status: 'completed', events: [] })
        const wrapper = mount(VNextPlayerApp)
        await flushPromises()

        await wrapper.get('.primary').trigger('click')
        await flushPromises()
        expect(api.playerRuntimeRun).not.toHaveBeenCalled()
        expect(document.body.textContent).toContain('D:\\Sandbox\\cache')

        const confirmButton = Array.from(document.body.querySelectorAll('button')).find(
            (button) => button.textContent?.includes('确认并运行'),
        ) as HTMLButtonElement
        confirmButton.click()
        await flushPromises()
        expect(api.playerRuntimeRun).toHaveBeenCalledWith(expect.objectContaining({
            dangerous_confirmations: [{ confirmation_id: 'sha256:confirm', confirmed: true }],
        }))
        wrapper.unmount()
    })

    it('组件卸载后停止会话轮询', async () => {
        vi.useFakeTimers()
        try {
            api.playerRuntimeRun.mockResolvedValue({ execution_id: 'run_1', status: 'queued', events: [] })
            const wrapper = mount(VNextPlayerApp)
            await flushPromises()

            void wrapper.get('.primary').trigger('click')
            await flushPromises()
            wrapper.unmount()
            await vi.advanceTimersByTimeAsync(300)

            expect(api.runStatus).not.toHaveBeenCalled()
        } finally {
            vi.useRealTimers()
        }
    })

    it('显式环境检查并保存可复用配置方案', async () => {
        api.playerRuntimePreflight.mockResolvedValue({
            ready: true,
            target_id: null,
            checked_at: '2026-08-29T00:00:00Z',
            duration_ms: 12,
            checks: [{ id: 'bundle', status: 'pass', message: 'Player 包检查通过' }],
        })
        api.savePlayerRuntimeProfile.mockResolvedValue({
            saved: true,
            profile: {
                profile_id: 'profile_1', name: '默认方案', target_id: null, values: {},
                revision: 1, image_overrides: {},
                created_at: '2026-08-29T00:00:00Z', updated_at: '2026-08-29T00:00:00Z',
            },
        })
        const wrapper = mount(VNextPlayerApp)
        await flushPromises()

        await wrapper.get('.tool-heading button').trigger('click')
        await flushPromises()
        expect(wrapper.get('.environment-report').text()).toContain('环境可运行')
        expect(wrapper.get('.environment-report').text()).toContain('Player 包检查通过')

        await wrapper.get('.profile-actions input').setValue('默认方案')
        await wrapper.get('.profile-actions button').trigger('click')
        await flushPromises()
        expect(api.savePlayerRuntimeProfile).toHaveBeenCalledWith(expect.objectContaining({ name: '默认方案' }))
        expect(wrapper.get('.runtime-tools select').text()).toContain('默认方案')
        wrapper.unmount()
    })

    it('运行录制默认关闭并由终端用户确认到精确方案 revision', async () => {
        const target = {
            target_id: 'target_1', name: '桌面', type: 'windows', window_title: 'Game',
            window_match: 'contains', work_area: { mode: 'client' }, allow_physical_fallback: true,
        }
        const recording = {
            enabled: true, strategy: 'changed_frames', target_fps: 15,
            max_duration_ms: 1_800_000, max_session_bytes: 2_147_483_648,
            min_free_bytes: 536_870_912, confirmed_profile_revision: 1,
        }
        api.playerRuntimeBootstrap.mockResolvedValue({
            available: true, form, targets: [target], default_target_id: 'target_1',
            assets: { categories: [], assets: [] },
            bundle: { project_id: 'project_1', release_id: 'release_1', name: '测试包' },
        })
        api.playerRuntimeProfiles.mockResolvedValue({ profiles: [{
            profile_id: 'profile_1', name: '录制方案', target_id: 'target_1', values: {},
            revision: 1, image_overrides: {}, recording,
            created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z',
        }] })
        api.savePlayerRuntimeProfile.mockResolvedValue({ saved: true, profile: {
            profile_id: 'profile_1', name: '录制方案', target_id: 'target_1', values: {},
            revision: 2, image_overrides: {}, recording: { ...recording, confirmed_profile_revision: 2 },
            created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:01:00Z',
        } })
        api.playerRuntimeRun.mockResolvedValue({
            execution_id: 'run_recording', status: 'completed', events: [],
            recording: { active: true, status: 'recording', frame_count: 8, disk_bytes: 4096 },
        })
        api.playerRuntimeRecordingStatus.mockResolvedValue({
            active: true, status: 'recording', frame_count: 8, disk_bytes: 4096,
        })
        const wrapper = mount(VNextPlayerApp)
        await flushPromises()

        await wrapper.get('.runtime-tools > label select').setValue('profile_1')
        await flushPromises()
        expect(wrapper.get('.recording-settings summary').text()).toContain('已启用')
        await wrapper.get('.profile-actions button').trigger('click')
        await flushPromises()
        expect(api.savePlayerRuntimeProfile).toHaveBeenCalledWith(expect.objectContaining({
            expected_revision: 1,
            recording: expect.objectContaining({
                enabled: true,
                strategy: 'changed_frames',
                confirm_current_revision: true,
            }),
        }))

        await wrapper.get('.primary').trigger('click')
        await flushPromises()
        expect(api.playerRuntimeRun).toHaveBeenCalledWith(expect.objectContaining({
            profile_id: 'profile_1', profile_revision: 2,
        }))
        expect(api.playerRuntimeRecordingSessions).toHaveBeenCalledTimes(2)
        expect(wrapper.get('.recording-runtime').text()).toContain('正在录制')
        await wrapper.get('.recording-runtime button').trigger('click')
        await flushPromises()
        expect(api.stopPlayerRuntimeRecording).toHaveBeenCalledTimes(1)
        expect(wrapper.find('.recording-runtime').exists()).toBe(false)
        wrapper.unmount()
    })

    it('Android 本机目标使用与 Windows/ADB 相同的录制配置入口', async () => {
        api.playerRuntimeBootstrap.mockResolvedValue({
            available: true, form,
            targets: [{ target_id: 'phone', name: '本机', type: 'android_local' }],
            default_target_id: 'phone', assets: { categories: [], assets: [] },
            bundle: { project_id: 'project_1', release_id: 'release_1', name: '测试包' },
        })
        const wrapper = mount(VNextPlayerApp)
        await flushPromises()

        expect(wrapper.find('.recording-settings').exists()).toBe(true)
        expect(wrapper.get('.recording-settings input[type="checkbox"]').attributes('disabled')).toBeUndefined()
        expect(wrapper.text()).not.toContain('尚未经过真实 APK 闭环验证')
        wrapper.unmount()
    })

    it('在共享 Player 内浏览录制帧并通过项目内确认框删除记录', async () => {
        api.playerRuntimeRecordingSessions.mockResolvedValue({ sessions: [{
            session_id: 'rec_1', started_at: '2026-09-03T05:36:00Z', status: 'completed',
            target_title: 'Android 本机', frame_count: 2, disk_bytes: 4096, final: true,
        }] })
        api.playerRuntimeRecordingSession.mockResolvedValue({
            session_id: 'rec_1', started_at: '2026-09-03T05:36:00Z', status: 'completed',
            frame_count: 2, disk_bytes: 4096,
            frames: [
                { frame_id: 'frame_1', sequence: 1, width: 720, height: 1280 },
                { frame_id: 'frame_2', sequence: 2, width: 720, height: 1280 },
            ],
        })
        api.playerRuntimeRecordingFrame.mockImplementation((_id: string, sequence: number) => Promise.resolve({
            frame: { frame_id: `frame_${sequence}`, sequence }, mime_type: 'image/png', data_base64: 'aGVsbG8=',
        }))
        api.deletePlayerRuntimeRecordingSession.mockResolvedValue({ deleted: true, session_id: 'rec_1' })
        const wrapper = mount(VNextPlayerApp)
        await flushPromises()

        await wrapper.get('.recording-settings summary').trigger('click')
        await wrapper.get('.recording-session-row').trigger('click')
        await flushPromises()
        expect(wrapper.get('.recording-viewer img').attributes('src')).toBe('data:image/png;base64,aGVsbG8=')
        await wrapper.findAll('.recording-viewer footer button')[1].trigger('click')
        await flushPromises()
        expect(api.playerRuntimeRecordingFrame).toHaveBeenLastCalledWith('rec_1', 2)

        await wrapper.get('.recording-viewer .danger-text').trigger('click')
        await flushPromises()
        expect(document.body.textContent).toContain('删除录制记录')
        ;(document.querySelector('[role="alertdialog"] .vnext-button.is-solid') as HTMLButtonElement).click()
        await flushPromises()
        expect(api.deletePlayerRuntimeRecordingSession).toHaveBeenCalledWith('rec_1')
        expect(wrapper.find('.recording-viewer').exists()).toBe(false)
        wrapper.unmount()
    })

    it('按 schema3 方案基线只提交本次改动，并让方案目标保持后端优先级', async () => {
        api.playerRuntimeProfiles.mockResolvedValue({ profiles: [{
            profile_id: 'profile_1', name: '三次运行', target_id: null, values: { count: 3 },
            revision: 1, image_overrides: {},
            created_at: '2026-08-29T00:00:00Z', updated_at: '2026-08-29T00:00:00Z',
        }] })
        api.playerRuntimeRun.mockResolvedValue({ execution_id: 'run_profile', status: 'completed', events: [] })
        const wrapper = mount(VNextPlayerApp)
        await flushPromises()

        await wrapper.get('.runtime-tools select').setValue('profile_1')
        await wrapper.get('.runtime-form input').setValue('5')
        await wrapper.get('.primary').trigger('click')
        await flushPromises()

        expect(api.playerRuntimeRun).toHaveBeenCalledWith({
            profile_id: 'profile_1',
            profile_revision: 1,
            player_values: { count: 5 },
            action_control_id: '',
        })
        wrapper.unmount()
    })

    it('只显示后端许可的当前平台动作，并用原生确认原子更新方案 revision', async () => {
        let eventSource: { onmessage: ((event: MessageEvent) => void) | null; close: ReturnType<typeof vi.fn> } | null = null
        class FakeEventSource {
            onmessage: ((event: MessageEvent) => void) | null = null
            onerror: (() => void) | null = null
            close = vi.fn()
            constructor() { eventSource = this }
        }
        vi.stubGlobal('EventSource', FakeEventSource)
        const captureForm: any = structuredClone(form)
        captureForm.pages[0].controls = [{
            control_id: 'point', type: 'coordinate', label: '点击坐标', help: '', default: { x: 1, y: 2 },
            options: [], required: false,
            binding: { kind: 'project_variable', variable_id: 'variable-point' },
            layout: { span: 12 },
            parameter_ui: { control: 'coordinate', actions: [{ id: 'pick-point', capture_kind: 'point', platforms: ['windows'] }] },
            terminal_actions: [{ action_id: 'pick-point', platforms: ['windows'] }],
            constraints: {}, platforms: ['windows'], source_type: 'point', type_fingerprint: 'sha256:point',
        }]
        api.playerRuntimeBootstrap.mockResolvedValue({
            available: true,
            form: captureForm,
            targets: [{
                target_id: 'target_1', name: '桌面', type: 'windows', window_title: 'Game',
                window_match: 'contains', work_area: { mode: 'client' }, allow_physical_fallback: true,
            }, {
                target_id: 'target_2', name: '备用桌面', type: 'windows', window_title: 'Game 2',
                window_match: 'contains', work_area: { mode: 'client' }, allow_physical_fallback: true,
            }],
            assets: { categories: [], assets: [] },
            default_target_id: 'target_1',
            bundle: { project_id: 'project_1', release_id: 'release_1', name: '测试包' },
        })
        api.playerRuntimeProfiles.mockResolvedValue({ profiles: [{
            profile_id: 'profile_1', name: '桌面方案', target_id: 'target_1', values: { point: { x: 3, y: 4 } },
            revision: 1, image_overrides: {},
            created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z',
        }] })
        const destination = {
            product_id: 'project_1', release_id: 'release_1', profile_id: 'profile_1',
            control_id: 'point', action_id: 'pick-point', profile_revision: 1, target_id: 'target_1',
        }
        api.playerRuntimeActions.mockImplementation(async (profileId: string) => ({
            platform: profileId ? 'windows' : null,
            profile_id: profileId || null,
            profile_revision: profileId ? 1 : null,
            blocked_reason: profileId ? '' : '请先保存方案',
            actions: profileId ? [{
                control_id: 'point', action_id: 'pick-point', platform: 'windows',
                capability: 'player.capture.point', enabled: true, disabled_reason: '', destination,
            }] : [],
        }))
        api.startPlayerControlCapture.mockResolvedValue({
            ok: true, capture_id: 'player_capture_1', state: 'capturing', destination,
        })
        api.confirmPlayerControlCapture.mockResolvedValue({
            ok: true, value: { x: 8, y: 9 }, profile: {
                profile_id: 'profile_1', name: '桌面方案', target_id: 'target_1', values: { point: { x: 8, y: 9 } },
                revision: 2, image_overrides: {},
                created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:01:00Z',
            },
        })
        const wrapper = mount(VNextPlayerApp, { attachTo: document.body })
        await flushPromises()
        await wrapper.get('.runtime-tools select').setValue('profile_1')
        await flushPromises()

        expect(wrapper.get('.terminal-actions').text()).toContain('拾取坐标')
        const focusedField = wrapper.get('.value-vector input').element as HTMLInputElement
        focusedField.focus()
        expect(document.activeElement).toBe(focusedField)
        await wrapper.get('.terminal-actions > button').trigger('click')
        await flushPromises()
        expect(document.activeElement).not.toBe(focusedField)
        expect(api.startPlayerControlCapture).toHaveBeenCalledWith(destination, window.location.origin)
        ;(eventSource as any)?.onmessage?.({ data: JSON.stringify({
            event: 'capture-command', request_id: 'native_request_1',
            field_request_id: 'player_capture_1', kind: 'field_confirm',
            snapshot_id: 'snap_1', point: [8, 9],
        }) } as MessageEvent)
        await flushPromises()

        expect(api.confirmPlayerControlCapture).toHaveBeenCalledWith(
            'player_capture_1', destination, expect.objectContaining({ point: [8, 9] }),
        )
        expect(api.acknowledgeCaptureAction).toHaveBeenCalledWith('native_request_1', { ok: true })
        expect(wrapper.findAll('.value-vector input').map((input) => input.attributes('value'))).toEqual(['8', '9'])
        expect(document.activeElement).not.toBe(focusedField)
        await vi.waitFor(() => expect(wrapper.get('[data-control-id="point"]').classes()).toContain('capture-return-highlight'))

        api.playerRuntimeActions.mockResolvedValue({
            platform: null, profile_id: 'profile_1', profile_revision: 2,
            blocked_reason: '请先把当前目标保存到配置方案', actions: [],
        })
        await wrapper.get('.runtime-panel > label select').setValue('')
        await flushPromises()
        expect(wrapper.get('.profile-notice').text()).toContain('请先把当前目标保存到配置方案')
        wrapper.unmount()
        vi.unstubAllGlobals()
    })

    it('无操作目标也可通过系统选择器填入强类型文件引用，确认前不改值', async () => {
        const fileForm: any = structuredClone(form)
        fileForm.pages[0].controls = [{
            control_id: 'input_file', type: 'file', label: '输入数据', help: '选择 JSON 数据文件',
            options: [], required: true,
            binding: { kind: 'project_variable', variable_id: 'variable-input-file' },
            layout: { span: 12 },
            parameter_ui: { control: 'file', actions: [{ id: 'choose-file-read', platforms: ['windows', 'android_adb', 'android_local'] }] },
            terminal_actions: [{ action_id: 'choose-file-read', platforms: ['windows', 'android_adb', 'android_local'] }],
            constraints: { extensions: ['.json'] }, platforms: ['windows', 'android_adb', 'android_local'],
            source_type: 'file_ref<read>', type_fingerprint: 'sha256:file-read',
        }]
        api.playerRuntimeBootstrap.mockResolvedValue({
            available: true,
            form: fileForm,
            targets: [],
            assets: { categories: [], assets: [] },
            default_target_id: null,
            bundle: { project_id: 'project_1', release_id: 'release_1', name: '无目标文件工具' },
        })
        api.playerRuntimeProfiles.mockResolvedValue({ profiles: [{
            profile_id: 'profile_file', name: '处理方案', target_id: null, values: {},
            revision: 1, image_overrides: {},
            created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:00:00Z',
        }] })
        const destination = {
            product_id: 'project_1', release_id: 'release_1', profile_id: 'profile_file',
            control_id: 'input_file', action_id: 'choose-file-read', profile_revision: 1, target_id: '',
        }
        api.playerRuntimeActions.mockImplementation(async (profileId: string) => ({
            platform: profileId ? 'windows' : null,
            profile_id: profileId || null,
            profile_revision: profileId ? 1 : null,
            blocked_reason: profileId ? '' : '请先保存方案',
            actions: profileId ? [{
                control_id: 'input_file', action_id: 'choose-file-read', platform: 'windows',
                capability: 'player.file.choose_read', enabled: true, disabled_reason: '', destination,
            }] : [],
        }))
        api.startPlayerControlCapture.mockResolvedValue({
            ok: true,
            capture_id: 'player_file_1',
            state: 'awaiting_confirmation',
            destination,
            candidate: {
                candidate_id: 'candidate_file_1', kind: 'file',
                display_name: 'tasks.json', access: ['read'],
            },
        })
        const reference = {
            kind: 'file_ref', platform: 'windows', source: 'player_system_picker',
            display_name: 'tasks.json', path: 'D:\\Data\\tasks.json',
            authorization_root: 'D:\\Data', authorization_root_id: 'windows:data', access: ['read'],
        }
        api.confirmPlayerControlCapture.mockResolvedValue({
            ok: true,
            value: reference,
            profile: {
                profile_id: 'profile_file', name: '处理方案', target_id: null,
                values: { input_file: reference }, revision: 2, image_overrides: {},
                created_at: '2026-09-01T00:00:00Z', updated_at: '2026-09-01T00:01:00Z',
            },
        })

        const wrapper = mount(VNextPlayerApp)
        await flushPromises()
        await wrapper.get('.runtime-tools select').setValue('profile_file')
        await flushPromises()

        expect(wrapper.get('.reference-summary').text()).toContain('尚未选择文件')
        await wrapper.get('.terminal-actions > button').trigger('click')
        await flushPromises()
        expect(api.confirmPlayerControlCapture).toHaveBeenCalledWith(
            'player_file_1', destination,
            { kind: 'native-reference', candidate_id: 'candidate_file_1' },
        )
        expect(wrapper.get('.reference-summary').text()).toContain('tasks.json')
        expect(wrapper.text()).not.toContain('D:\\Data\\tasks.json')
        wrapper.unmount()
    })
})
