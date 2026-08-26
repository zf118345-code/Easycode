import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import PlatformScheduleDialog from '@/components/PlatformScheduleDialog.vue'
import { platformApi } from '@/api/platformApi'

vi.mock('@/api/platformApi', () => ({
    platformApi: {
        listSchedules: vi.fn(),
        saveSchedule: vi.fn(),
        deleteSchedule: vi.fn(),
        outboxStatus: vi.fn()
    }
}))

describe('PlatformScheduleDialog', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        platformApi.listSchedules.mockResolvedValue({ schedules: [] })
        platformApi.outboxStatus.mockResolvedValue({ pending: 0, dead: 0 })
        platformApi.saveSchedule.mockResolvedValue({ id: 'schedule-1' })
    })

    it('加载 IDE 计划与离线队列状态', async () => {
        platformApi.listSchedules.mockResolvedValue({
            schedules: [{
                id: 's1', name: '定时启动', schedule_type: 'daily', schedule_value: '08:00:00',
                payload: { task_id: 't1', node_id: 'n1' }, enabled: true, next_run_at: null,
            }]
        })
        platformApi.outboxStatus.mockResolvedValue({ pending: 2, dead: 1 })
        const wrapper = mount(PlatformScheduleDialog, {
            props: { modelValue: true, scope: 'ide', tasks: [] },
            global: { stubs: { teleport: true } }
        })
        await wrapper.vm.load()
        await flushPromises()
        expect(platformApi.listSchedules).toHaveBeenCalledWith('ide')
        expect(wrapper.vm.schedules[0].name).toBe('定时启动')
        expect(wrapper.vm.outbox.pending).toBe(2)
    })

    it('编辑间隔计划时转为数字，Player 计划保存实例与配置方案', async () => {
        const wrapper = mount(PlatformScheduleDialog, {
            props: { modelValue: true, scope: 'player', instanceId: 'instance-2', profiles: [] },
            global: { stubs: { teleport: true } }
        })
        wrapper.vm.edit({
            id: 's1', name: '轮询', schedule_type: 'interval', schedule_value: '30', enabled: true,
            payload: { profile_name: '夜间方案' },
        })
        expect(wrapper.vm.draft.schedule_value).toBe(30)
        await wrapper.vm.save()
        await flushPromises()
        expect(platformApi.saveSchedule).toHaveBeenCalledWith(expect.objectContaining({
            id: 's1', schedule_type: 'interval', schedule_value: '30',
            payload: { instance_id: 'instance-2', profile_name: '夜间方案' },
        }), 'player')
    })
})
