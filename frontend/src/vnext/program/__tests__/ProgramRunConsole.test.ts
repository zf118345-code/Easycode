import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ProgramRunConsole from '../ProgramRunConsole.vue'
import type { RuntimeSession } from '../../types'

function session(executionId = 'execution-1234567890'): RuntimeSession {
    return {
        execution_id: executionId,
        status: 'completed',
        started_at: '2026-09-01T00:00:00Z',
        finished_at: '2026-09-01T00:00:02Z',
        error: '',
        events: [
            {
                sequence: 1,
                timestamp: '2026-09-01T00:00:01Z',
                level: 'info',
                category: 'script',
                message: '开始执行',
                instruction_id: 'stmt-1',
            },
            {
                sequence: 2,
                timestamp: '2026-09-01T00:00:02Z',
                level: 'warning',
                category: 'vision',
                message: '没有找到图片',
                instruction_id: 'stmt-2',
            },
        ],
        current_instruction_id: '',
        current_source: {},
        variables: {},
        breakpoints: [],
        diagnostic_available: false,
        failure_frame_available: false,
    }
}

describe('ProgramRunConsole', () => {
    it('defaults to all events and filters by real event category', async () => {
        const wrapper = mount(ProgramRunConsole, { props: { session: session() } })

        expect(wrapper.text()).toContain('2 条')
        expect(wrapper.text()).toContain('开始执行')
        expect(wrapper.text()).toContain('没有找到图片')

        const visionTab = wrapper.findAll('.category-tabs button')
            .find((button) => button.text().includes('图像'))
        expect(visionTab).toBeTruthy()
        await visionTab!.trigger('click')

        expect(wrapper.text()).not.toContain('开始执行')
        expect(wrapper.text()).toContain('没有找到图片')
        expect(wrapper.text()).toContain('1 条')
    })

    it('clears only the current view and resets that view for a new execution', async () => {
        const wrapper = mount(ProgramRunConsole, { props: { session: session() } })
        await wrapper.get('[aria-label="清空当前视图，不删除诊断日志"]').trigger('click')

        expect(wrapper.text()).toContain('本次运行没有可显示的日志')
        expect(wrapper.props('session')?.events).toHaveLength(2)

        await wrapper.setProps({ session: session('execution-new') })
        expect(wrapper.text()).toContain('开始执行')
        expect(wrapper.text()).toContain('2 条')
    })

    it('emits close from the compact icon action', async () => {
        const wrapper = mount(ProgramRunConsole, { props: { session: null } })
        await wrapper.get('[aria-label="关闭日志"]').trigger('click')
        expect(wrapper.emitted('close')).toHaveLength(1)
    })

    it('shows named local results and project variables without exposing stable ids', async () => {
        const current = session()
        current.status = 'paused'
        current.value_entries = {
            local: [{
                id: 'symbol_opaque_123', display_name: '当前体力', value_type: 'int64',
                kind: 'local', value: 86,
            }],
            project: [{
                id: 'variable_opaque_456', display_name: '最低体力', value_type: 'int64',
                kind: 'project', value: 18,
            }],
        }
        const wrapper = mount(ProgramRunConsole, { props: { session: current } })

        await wrapper.get('.console-mode-tabs button:nth-child(2)').trigger('click')

        expect(wrapper.text()).toContain('当前体力')
        expect(wrapper.text()).toContain('最低体力')
        expect(wrapper.text()).toContain('86')
        expect(wrapper.text()).not.toContain('symbol_opaque_123')
    })

    it('locates the statement represented by a runtime event', async () => {
        const wrapper = mount(ProgramRunConsole, { props: { session: session() } })

        await wrapper.get('.event-row').trigger('click')

        expect(wrapper.emitted('locateStatement')).toEqual([['stmt-1']])
    })
})
