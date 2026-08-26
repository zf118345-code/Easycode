import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RuntimeServicesPanel from '@/components/panels/RuntimeServicesPanel.vue'
import { platformApi } from '@/api/platformApi'

vi.mock('@/api/platformApi', () => ({
    platformApi: {
        overview: vi.fn(), listStates: vi.fn(), listMessages: vi.fn(), listLeases: vi.fn(),
        setState: vi.fn(), deleteState: vi.fn(), publishMessage: vi.fn(), claimMessages: vi.fn(), ackMessage: vi.fn(),
        acquireLease: vi.fn(), releaseLease: vi.fn(), publishRemote: vi.fn(), claimRemote: vi.fn(), ackRemote: vi.fn(),
        acquireRemoteLease: vi.fn(), renewRemoteLease: vi.fn(), releaseRemoteLease: vi.fn()
    }
}))

describe('RuntimeServicesPanel Player reuse', () => {
    let pinia

    beforeEach(() => {
        pinia = createPinia()
        setActivePinia(pinia)
        vi.clearAllMocks()
        platformApi.overview.mockResolvedValue({ counts: {}, database: 'player.db' })
        platformApi.publishRemote.mockResolvedValue({ success: true, queued: false })
        platformApi.acquireRemoteLease.mockResolvedValue({ token: 'lease-token' })
    })

    it('没有 IDE Pinia 时仍可加载 Player 独立运行服务', async () => {
        const wrapper = mount(RuntimeServicesPanel, {
            props: { scope: 'player', instanceId: 'instance-3', profiles: [] },
            global: { plugins: [pinia], stubs: { PlatformScheduleDialog: true } }
        })
        await flushPromises()

        expect(platformApi.overview).toHaveBeenCalledWith('player')
        expect(wrapper.vm.consumer).toBe('instance-3')
        expect(wrapper.vm.tasks).toEqual([])
    })

    it('Player 的远程消息使用 Player outbox，远程租约返回令牌', async () => {
        const wrapper = mount(RuntimeServicesPanel, {
            props: { scope: 'player', instanceId: 'instance-2' },
            global: { plugins: [pinia], stubs: { PlatformScheduleDialog: true } }
        })
        Object.assign(wrapper.vm.remote, { endpoint: 'http://pc-a:8000', token: 'secret', channel: 'team', payload: '{"ready":true}' })
        await wrapper.vm.publishRemote()
        expect(platformApi.publishRemote).toHaveBeenCalledWith(expect.objectContaining({ channel: 'team', payload: { ready: true } }), 'player')

        Object.assign(wrapper.vm.remoteLease, { resource_key: 'account-1', owner: 'instance-2', ttl_seconds: 30 })
        await wrapper.vm.acquireRemoteLease()
        expect(platformApi.acquireRemoteLease).toHaveBeenCalledWith(expect.objectContaining({ resource_key: 'account-1' }))
        expect(wrapper.vm.remoteLeaseToken).toBe('lease-token')
    })
})
