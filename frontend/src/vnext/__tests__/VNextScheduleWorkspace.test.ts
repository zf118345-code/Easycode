import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
    hubStatus: vi.fn(), plans: vi.fn(), batches: vi.fn(), occurrences: vi.fn(),
    diagnostics: vi.fn(), dispatches: vi.fn(), installAgent: vi.fn(),
    registerInstallation: vi.fn(), savePlan: vi.fn(), deletePlan: vi.fn(),
    saveBatch: vi.fn(), deleteBatch: vi.fn(), openInstance: vi.fn(),
    createInstance: vi.fn(), bindRelease: vi.fn(),
    lanStatus: vi.fn(), lanDiagnostics: vi.fn(), startLan: vi.fn(), stopLan: vi.fn(),
    createPairingSession: vi.fn(), discoverLan: vi.fn(), beginPairing: vi.fn(),
    completePairing: vi.fn(), confirmPairing: vi.fn(), setLanPermissions: vi.fn(),
    revokeLanPeer: vi.fn(), refreshLanPeer: vi.fn(),
}))

vi.mock('../scheduleApi', () => ({ scheduleApi: api }))

import VNextScheduleWorkspace from '../components/VNextScheduleWorkspace.vue'

const status = {
    available: true, ready: true, host_id: 'host-local', owner_scope: 'current_windows_user',
    checked_at: '2026-09-01T00:00:00Z', installations: [], active_run_count: 0,
    interactive_session: { state: 'ready' },
    wake_agent: { available: true, installed: false, state: 'not_installed' },
    remote_dispatch: { available: false, state: 'not_authorized_or_not_implemented', error_id: 'schedule.remote_dispatch_unavailable' },
    android_system_scheduler: { available: false, state: 'not_implemented', error_id: 'schedule.android_scheduler_unavailable' },
    registry_error: null,
}

describe('VNextScheduleWorkspace', () => {
    afterEach(() => { vi.unstubAllGlobals() })

    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        api.hubStatus.mockResolvedValue(structuredClone(status))
        api.plans.mockResolvedValue([])
        api.batches.mockResolvedValue([])
        api.occurrences.mockResolvedValue([])
        api.diagnostics.mockResolvedValue([])
        api.lanDiagnostics.mockResolvedValue([])
        api.lanStatus.mockResolvedValue({
            available: true, running: false,
            identity: { host_id: 'host-local', device_name: '本机', platform: 'windows', public_key: 'key', fingerprint: 'fingerprint' },
            addresses: [], port: 41663, permissions: ['messages', 'status', 'remote_start'],
            paired_devices: [], remote_instances: [], pairing_sessions: [],
            cloud_relay: { available: false, state: 'not_in_product_scope' },
        })
        api.installAgent.mockResolvedValue({ ok: true })
    })

    it('renders only real empty states and an actionable Windows Agent state', async () => {
        const wrapper = mount(VNextScheduleWorkspace)
        await flushPromises()

        expect(wrapper.text()).toContain('还没有运行计划')
        expect(wrapper.text()).toContain('计划 Agent 未启用')
        expect(wrapper.text()).not.toContain('在线设备')
        await wrapper.get('.agent-state button').trigger('click')
        await flushPromises()
        expect(api.installAgent).toHaveBeenCalledTimes(1)
    })

    it('keeps plans, reusable batches and installed instances as separate navigation', async () => {
        const wrapper = mount(VNextScheduleWorkspace)
        await flushPromises()
        const labels = wrapper.findAll('.schedule-nav nav button').map(item => item.text())
        expect(labels).toEqual(['计划0', '批次0', '实例0', '启动方式0'])

        await wrapper.findAll('.schedule-nav nav button')[1].trigger('click')
        expect(wrapper.text()).toContain('还没有可复用批次')
        await wrapper.findAll('.schedule-nav nav button')[2].trigger('click')
        expect(wrapper.text()).toContain('尚未登记签名 Player')
    })

    it('keeps ordinary plan fields in direct rows and groups one trigger choice', async () => {
        api.batches.mockResolvedValue([{
            batch_id: 'batch-1', revision: 1, name: '每日批次',
            dispatch_mode: 'simultaneous', entries: [],
        }])
        const wrapper = mount(VNextScheduleWorkspace)
        await flushPromises()

        await wrapper.get('.heading-actions .primary').trigger('click')
        const nameField = wrapper.findAll('.form-scroll > .field').find(field => field.get(':scope > span:first-child').text() === '计划名称')
        expect(nameField).toBeTruthy()
        expect(nameField?.find(':scope > input').exists()).toBe(true)
        expect(wrapper.findAll('.choice-row .choice-options label')).toHaveLength(3)
        expect(wrapper.find('.schedule-dialog-backdrop').exists()).toBe(false)
    })

    it('keeps the workspace visible until a compact inspector is explicitly opened', async () => {
        const removeEventListener = vi.fn()
        vi.stubGlobal('matchMedia', vi.fn(() => ({
            matches: true,
            addEventListener: vi.fn(),
            removeEventListener,
        })))
        const wrapper = mount(VNextScheduleWorkspace, { attachTo: globalThis.document.body })
        await flushPromises()

        expect(wrapper.find('.schedule-main').exists()).toBe(true)
        expect(wrapper.find('.schedule-inspector').exists()).toBe(false)

        await wrapper.findAll('.schedule-nav nav button')[2].trigger('click')
        await wrapper.get('.compact-empty button').trigger('click')
        await wrapper.vm.$nextTick()
        expect(wrapper.find('.schedule-inspector.is-drawer').exists()).toBe(true)
        expect(wrapper.find('.schedule-inspector-scrim').exists()).toBe(true)
        expect(globalThis.document.activeElement).toBe(wrapper.get('[aria-label="关闭计划中心检查器"]').element)

        await wrapper.get('.schedule-inspector').trigger('keydown', { key: 'Escape' })
        await wrapper.vm.$nextTick()
        expect(wrapper.find('.schedule-inspector').exists()).toBe(false)
        wrapper.unmount()
        expect(removeEventListener).toHaveBeenCalled()
    })
})
