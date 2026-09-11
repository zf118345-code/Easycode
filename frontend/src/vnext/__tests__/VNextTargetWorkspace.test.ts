import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
    targets: vi.fn(),
    saveTargets: vi.fn(),
    targetReferences: vi.fn(),
    adbCandidates: vi.fn(),
    testWindowsTarget: vi.fn(),
}))

const captureSessionMock = vi.hoisted(() => ({ captureWindow: vi.fn() }))

vi.mock('../captureSession', () => ({ vnextCaptureSession: captureSessionMock }))

vi.mock('../api', async () => {
    const actual = await vi.importActual<typeof import('../api')>('../api')
    return { ...actual, vnextApi: { ...actual.vnextApi, ...apiMocks } }
})

import { VNextApiError } from '../api'
import { useVNextStore } from '../store'
import type { TargetDefinition } from '../types'
import VNextTargetWorkspace from '../components/VNextTargetWorkspace.vue'

const workspace = {
    workspace_id: 'workspace-target-ui', generation: 3, project_id: 'project-target-ui',
    project_name: '目标界面', project_path: 'D:/Projects/TargetUi', read_only: false,
}
const windowsTarget: TargetDefinition = {
    target_id: 'target-window', name: '游戏窗口', type: 'windows', window_title: '传奇',
    window_match: 'contains', work_area: { mode: 'client' }, allow_physical_fallback: true,
}
const adbTarget: TargetDefinition = {
    target_id: 'target-adb', name: '雷电模拟器', type: 'android_adb', device_serial: 'emulator-5554',
}

function setup(targets: TargetDefinition[] = [], defaultTargetId: string | null = null) {
    const pinia = createPinia()
    setActivePinia(pinia)
    const store = useVNextStore()
    store.workspace = workspace
    store.targets = targets
    store.defaultTargetId = defaultTargetId
    store.targetRevision = 'sha256:current'
    const wrapper = mount(VNextTargetWorkspace, { global: { plugins: [pinia] } })
    return { wrapper, store }
}

describe('format-6 target workspace', () => {
    beforeEach(() => {
        Object.values(apiMocks).forEach((mock) => mock.mockReset())
        apiMocks.targets.mockResolvedValue({ schema_version: 1, targets: [], default_target_id: null, revision: 'sha256:reload' })
        apiMocks.targetReferences.mockResolvedValue({ target_id: 'target-window', references: [] })
        apiMocks.adbCandidates.mockResolvedValue({
            available: true, code: 'ok', message: '', candidates: [
                { serial: 'emulator-5560', state: 'device', selectable: true, model: '雷电模拟器', product: '', transport_id: '4', display_name: '雷电模拟器' },
                { serial: 'USB-PHONE', state: 'unauthorized', selectable: false, model: '', product: '', transport_id: '5', display_name: 'USB-PHONE' },
            ],
        })
        apiMocks.testWindowsTarget.mockResolvedValue({
            ok: true, title: '超能世界', application: 'WeChatAppEx.exe', window_rect: [465, 0, 915, 840],
            binding_method: 'captured_instance', message: '已找到并高亮目标窗口',
        })
        apiMocks.saveTargets.mockImplementation(async (_workspace, _revision, targets, defaultTargetId) => ({
            schema_version: 1,
            targets,
            default_target_id: defaultTargetId,
            revision: `sha256:saved-${apiMocks.saveTargets.mock.calls.length}`,
        }))
    })

    it('starts with an honest no-target empty state and creates ADB only after explicit valid save', async () => {
        const { wrapper, store } = setup()
        expect(wrapper.text()).toContain('无操作目标')
        expect(wrapper.text()).toContain('当前默认运行方式')

        await wrapper.get('button[title="新建运行目标"]').trigger('click')
        await wrapper.get('input[value="android_adb"]').setValue(true)
        await wrapper.get('[data-testid="create-target-name"]').setValue('测试模拟器')
        await wrapper.get('[data-testid="create-target-adb-serial"]').setValue('emulator-5556')
        await wrapper.get('.create-target-dialog form').trigger('submit')

        await vi.waitFor(() => expect(apiMocks.saveTargets).toHaveBeenCalledTimes(1))
        const sentTargets = apiMocks.saveTargets.mock.calls[0]?.[2] as TargetDefinition[]
        expect(sentTargets[0]).toEqual(expect.objectContaining({
            name: '测试模拟器', type: 'android_adb', device_serial: 'emulator-5556',
        }))
        expect(sentTargets[0]).not.toHaveProperty('work_area')
        await vi.waitFor(() => expect(store.defaultTargetId).toBe(sentTargets[0]?.target_id))
        expect(wrapper.find('.create-target-dialog').exists()).toBe(false)
    })

    it('normalizes Windows desktop and custom region to strict work-area variants', async () => {
        const { wrapper, store } = setup([windowsTarget], 'target-window')
        expect(wrapper.findAll('.target-inspector .field.app-form-row').length).toBeGreaterThanOrEqual(4)
        expect(wrapper.get('.target-inspector .readonly-field').classes()).toContain('app-form-row')
        expect(wrapper.find('.target-inspector .readonly-field small').exists()).toBe(false)
        await wrapper.get('[data-testid="target-work-area"]').setValue('region')
        const regionInputs = wrapper.findAll('.target-inspector .region-grid input')
        await regionInputs[0]?.setValue('12')
        await regionInputs[1]?.setValue('20')
        await regionInputs[2]?.setValue('800')
        await regionInputs[3]?.setValue('600')
        await wrapper.get('.target-form').trigger('submit')
        await vi.waitFor(() => expect(apiMocks.saveTargets).toHaveBeenCalledTimes(1))
        await vi.waitFor(() => expect(store.targetBusy).toBe(false))
        expect(storeTargetArea(wrapper)).toBe('region')

        let sent = (apiMocks.saveTargets.mock.calls[0]?.[2] as TargetDefinition[])[0]
        expect(sent).toMatchObject({ type: 'windows', work_area: { mode: 'region', region: [12, 20, 800, 600] } })

        await wrapper.get('[data-testid="target-work-area"]').setValue('desktop')
        await wrapper.get('.target-form').trigger('submit')
        await vi.waitFor(() => expect(apiMocks.saveTargets).toHaveBeenCalledTimes(2))
        await vi.waitFor(() => expect(store.targetBusy).toBe(false))
        sent = (apiMocks.saveTargets.mock.calls[1]?.[2] as TargetDefinition[])[0]
        expect(sent).toMatchObject({ type: 'windows', window_title: '', work_area: { mode: 'desktop' }, allow_physical_fallback: true })
        if (!sent || sent.type !== 'windows') throw new Error('预期 Windows 目标')
        expect(sent.work_area).not.toHaveProperty('region')
    })

    it('captures a same-title Windows instance into the draft and clears it after manual title edits', async () => {
        captureSessionMock.captureWindow.mockImplementationOnce(async (handler) => handler({
            title: '超能世界', application: 'WeChatAppEx.exe', window_rect: [465, 0, 915, 840],
            binding: {
                binding_version: 1, binding_id: 'window_binding_right', title: '超能世界',
                class_name: 'Chrome_WidgetWin_1', executable_name: 'WeChatAppEx.exe',
                hwnd: 202, process_id: 1002, process_started_at_ms: 1000, captured_at: '2026-09-08T12:00:00+0800',
            },
        }))
        const { wrapper } = setup([windowsTarget], 'target-window')

        await wrapper.get('[data-testid="capture-target-window"]').trigger('click')
        expect((wrapper.get('[data-testid="target-window-title"]').element as HTMLInputElement).value).toBe('超能世界')
        expect(wrapper.text()).toContain('已捕获当前窗口实例')
        expect(apiMocks.saveTargets).not.toHaveBeenCalled()

        await wrapper.get('[data-testid="test-target-window"]').trigger('click')
        await vi.waitFor(() => expect(apiMocks.testWindowsTarget).toHaveBeenCalledTimes(1))
        expect(apiMocks.testWindowsTarget.mock.calls[0]?.[1]).toMatchObject({
            window_match: 'exact', window_binding: { hwnd: 202 },
        })

        await wrapper.get('[data-testid="target-window-title"]').setValue('另一个窗口')
        await wrapper.get('.target-form').trigger('submit')
        await vi.waitFor(() => expect(apiMocks.saveTargets).toHaveBeenCalledTimes(1))
        const sent = (apiMocks.saveTargets.mock.calls[0]?.[2] as TargetDefinition[])[0]
        expect(sent).not.toHaveProperty('window_binding')
    })

    it('offers explicit ADB candidates but only persists the author-selected serial', async () => {
        const { wrapper } = setup()
        await wrapper.get('button[title="新建运行目标"]').trigger('click')
        await wrapper.get('input[value="android_adb"]').setValue(true)
        await wrapper.get('[data-testid="create-target-name"]').setValue('候选模拟器')

        const picker = wrapper.get('[data-testid="adb-device-picker"]')
        await picker.get('button').trigger('click')
        await vi.waitFor(() => expect(apiMocks.adbCandidates).toHaveBeenCalledTimes(1))
        const choices = picker.findAll('[role="option"]')
        expect(choices).toHaveLength(2)
        expect(choices[1]?.attributes('disabled')).toBeDefined()
        expect((wrapper.get('[data-testid="create-target-adb-serial"]').element as HTMLInputElement).value).toBe('')

        await choices[0]?.trigger('click')
        expect((wrapper.get('[data-testid="create-target-adb-serial"]').element as HTMLInputElement).value).toBe('emulator-5560')
        expect(apiMocks.saveTargets).not.toHaveBeenCalled()

        await wrapper.get('.create-target-dialog form').trigger('submit')
        await vi.waitFor(() => expect(apiMocks.saveTargets).toHaveBeenCalledTimes(1))
        expect((apiMocks.saveTargets.mock.calls[0]?.[2] as TargetDefinition[])[0]).toMatchObject({
            type: 'android_adb', device_serial: 'emulator-5560',
        })
    })

    it('keeps ADB help attached to the control row instead of a separate permanent paragraph', () => {
        const { wrapper } = setup([adbTarget], 'target-adb')
        const serial = wrapper.get('[data-testid="target-adb-serial"]')
        const row = serial.element.closest('.app-form-row')
        expect(row).not.toBeNull()
        expect(row?.querySelector('.app-form-help')?.textContent).toContain('不会自动切换')
        expect(wrapper.find('.target-inspector section > p.field-help').exists()).toBe(false)
    })

    it('supports keyboard selection and exposes a recoverable inspector drawer state', async () => {
        const { wrapper } = setup([windowsTarget, adbTarget], 'target-window')
        expect(wrapper.get('[data-target-id="target-window"]').attributes('aria-selected')).toBe('true')

        await wrapper.get('.target-list').trigger('keydown', { key: 'ArrowDown' })
        expect(wrapper.get('[data-target-id="target-adb"]').attributes('aria-selected')).toBe('true')
        await wrapper.get('.primary-action').trigger('click')
        expect(wrapper.get('.target-inspector').classes()).toContain('is-open')
        expect(wrapper.find('.inspector-scrim').exists()).toBe(true)
        await wrapper.get('.target-inspector').trigger('keydown', { key: 'Escape' })
        expect(wrapper.get('.target-inspector').classes()).not.toContain('is-open')
        expect(wrapper.find('.inspector-scrim').exists()).toBe(false)
    })

    it('blocks deletion when references exist and emits a stable navigation target', async () => {
        apiMocks.targetReferences.mockResolvedValueOnce({
            target_id: 'target-window',
            references: [{ kind: 'program_value', function_id: 'func-main', function_name: '主程序', statement_id: 'stmt-target', value_id: 'value-target' }],
        })
        const { wrapper } = setup([windowsTarget], 'target-window')
        await wrapper.get('.danger-action').trigger('click')
        await vi.waitFor(() => expect(wrapper.text()).toContain('运行目标仍在使用'))
        expect(wrapper.find('.delete-dialog footer button.danger').exists()).toBe(false)

        await wrapper.get('.reference-list button').trigger('click')
        expect(wrapper.emitted('openReference')?.[0]?.[0]).toMatchObject({ function_id: 'func-main', statement_id: 'stmt-target' })
        expect(apiMocks.saveTargets).not.toHaveBeenCalled()
    })

    it('keeps the draft on 409 and reloads only after an explicit recovery action', async () => {
        apiMocks.saveTargets.mockRejectedValueOnce(new VNextApiError(
            '目标配置已经变化', 409, '', 'target_revision_conflict', false, 'reload_workspace',
            [{ expected_revision: 'sha256:current', actual_revision: 'sha256:external' }],
        ))
        apiMocks.targets.mockResolvedValueOnce({ schema_version: 1, targets: [adbTarget], default_target_id: 'target-adb', revision: 'sha256:external' })
        const { wrapper, store } = setup([windowsTarget], 'target-window')
        await wrapper.get('[data-testid="target-name"]').setValue('改名后的窗口')
        await wrapper.get('.target-form').trigger('submit')

        await vi.waitFor(() => expect(wrapper.text()).toContain('运行目标已在外部修改'))
        expect(store.targets[0]?.name).toBe('游戏窗口')
        expect(wrapper.get('[data-testid="target-name"]').element).toHaveProperty('value', '改名后的窗口')

        await wrapper.get('.compact-dialog footer .primary').trigger('click')
        await vi.waitFor(() => expect(store.targets[0]?.target_id).toBe('target-adb'))
        expect(apiMocks.targets).toHaveBeenCalledTimes(1)
        expect(store.targetConflict).toBeNull()
    })
})

function storeTargetArea(wrapper: ReturnType<typeof mount>): string {
    return (wrapper.get('[data-testid="target-work-area"]').element as HTMLSelectElement).value
}
