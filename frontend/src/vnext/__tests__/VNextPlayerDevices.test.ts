import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
    playerRuntimeLan: vi.fn(),
    playerRuntimeMessageInstance: vi.fn(),
    playerRuntimeMessages: vi.fn(),
}))

vi.mock('../playerApi', () => ({ vnextApi: api }))

import VNextPlayerDevices from '../components/VNextPlayerDevices.vue'

describe('VNextPlayerDevices', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        api.playerRuntimeLan.mockResolvedValue({
            available: true,
            running: false,
            addresses: ['192.168.1.10'],
            port: 41663,
            paired_devices: [],
            pairing_sessions: [],
        })
        api.playerRuntimeMessageInstance.mockResolvedValue({
            instance_id: 'instance-1',
            display_name: '本机 Player',
        })
        api.playerRuntimeMessages.mockResolvedValue({ copies: [] })
    })

    it('keeps ordinary device inputs in compact rows and combines address with port', async () => {
        const wrapper = mount(VNextPlayerDevices)
        const details = wrapper.get('details')
        ;(details.element as HTMLDetailsElement).open = true
        await details.trigger('toggle')
        await flushPromises()

        const instanceField = wrapper.get('.device-field')
        expect(instanceField.get(':scope > span:first-child').text()).toBe('本实例名称')
        expect(instanceField.find('.inline-edit input').exists()).toBe(true)
        expect(instanceField.find('.inline-edit button').text()).toContain('保存')

        await wrapper.findAll('.device-actions button')[1]!.trigger('click')
        const addressField = wrapper.get('.connect-card .device-field')
        expect(addressField.get(':scope > span:first-child').text()).toBe('设备地址')
        expect(addressField.findAll('.connect-address-control input')).toHaveLength(2)
        expect((addressField.get('.connect-port').element as HTMLInputElement).value).toBe('41663')
        expect(wrapper.find('.connect-card [role="dialog"]').exists()).toBe(false)
    })
})
