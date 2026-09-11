import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
    playerRuntimeSchedules: vi.fn(), savePlayerRuntimeSchedule: vi.fn(),
    deletePlayerRuntimeSchedule: vi.fn(), runPlayerRuntimeScheduleNow: vi.fn(),
}))
vi.mock('../playerApi', () => ({ vnextApi: api }))

import VNextPlayerSchedules from '../components/VNextPlayerSchedules.vue'
import type { PlayerProfile } from '../types'

const profile: PlayerProfile = {
    profile_id: 'profile_1', name: '每日任务', target_id: 'phone', values: {}, revision: 3,
    image_overrides: {}, recording: { enabled: false, strategy: 'changed_frames', target_fps: 15, max_duration_ms: 1000, max_session_bytes: 1000, min_free_bytes: 1000 },
    created_at: '', updated_at: '',
}

describe('VNextPlayerSchedules', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        api.playerRuntimeSchedules.mockResolvedValue({ schema_version: 1, schedules: [], occurrences: [] })
        api.savePlayerRuntimeSchedule.mockResolvedValue({ schedule_id: 'schedule_1' })
    })

    it('用面向用户的表单创建类型化每日计划', async () => {
        const wrapper = mount(VNextPlayerSchedules, { props: { profiles: [profile] } })
        await flushPromises()
        await wrapper.get('summary').trigger('click')
        await wrapper.get('.schedule-create').trigger('click')
        const nameField = wrapper.findAll('.schedule-editor label').find(item => item.get(':scope > span').text() === '名称')
        expect(nameField?.find(':scope > input').exists()).toBe(true)
        expect(wrapper.get('.schedule-enabled').get(':scope > span').text()).toBe('启用计划')
        await wrapper.get('.schedule-editor input[type="text"], .schedule-editor input:not([type])').setValue('早晨挂机')
        const selects = wrapper.findAll('.schedule-editor select')
        await selects[1].setValue('daily')
        await wrapper.get('input[type="time"]').setValue('07:30')
        await wrapper.get('.schedule-editor-actions .primary').trigger('click')
        await flushPromises()
        expect(api.savePlayerRuntimeSchedule).toHaveBeenCalledWith(expect.objectContaining({
            name: '早晨挂机', profile_id: 'profile_1',
            trigger: expect.objectContaining({ kind: 'daily', local_time: '07:30' }),
            overlap_policy: 'queue_once', misfire_policy: 'run_once',
        }))
    })

    it('立即运行复用计划且不改变下一次触发时间', async () => {
        api.playerRuntimeSchedules.mockResolvedValue({ schema_version: 1, schedules: [{
            schedule_id: 'schedule_1', revision: 1, name: '每小时', enabled: true,
            profile_id: 'profile_1', profile_name: '每日任务', profile_revision_at_save: 3,
            trigger: { kind: 'interval', anchor_time: '2026-09-03T00:00:00Z', interval_ms: 3_600_000 },
            misfire_policy: 'run_once', max_lateness_ms: 3_600_000, overlap_policy: 'queue_once',
            next_trigger_at: '2026-09-03T01:00:00Z',
        }], occurrences: [] })
        api.runPlayerRuntimeScheduleNow.mockResolvedValue({ accepted: true, schedule_id: 'schedule_1' })
        const wrapper = mount(VNextPlayerSchedules, { props: { profiles: [profile] } })
        await flushPromises()
        await wrapper.findAll('.schedule-row > button')[1].trigger('click')
        expect(api.runPlayerRuntimeScheduleNow).toHaveBeenCalledWith('schedule_1')
    })
})
