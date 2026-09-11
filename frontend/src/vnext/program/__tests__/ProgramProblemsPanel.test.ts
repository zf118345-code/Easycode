import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ProgramProblemsPanel from '../ProgramProblemsPanel.vue'

describe('ProgramProblemsPanel', () => {
    it('renders only real diagnostics, filters by severity and emits stable locations', async () => {
        const diagnostics = [
            { code: 'PGM-ARG-001', severity: 'error', message: '图片不能为空', function_id: 'func-main', statement_id: 'stmt-image', value_id: 'value-image', field_path: 'arguments.image' },
            { code: 'PGM-TRY-003', severity: 'warning', message: '需要确认重试风险', function_id: 'func-main', statement_id: 'stmt-try' },
        ]
        const wrapper = mount(ProgramProblemsPanel, {
            props: {
                diagnostics,
                programs: [{
                    document_id: 'doc-main', function_id: 'func-main', display_name: '主程序', statement_count: 2,
                    revision: 'revision', parameters: [], return_type: 'null', contract_version: '1.0.0', contract_fingerprint: 'fingerprint',
                }],
            },
        })

        expect(wrapper.text()).toContain('图片不能为空')
        expect(wrapper.text()).toContain('主程序 · arguments.image')
        await wrapper.findAll('.problem-row')[0].trigger('click')
        expect(wrapper.emitted('open')?.[0]?.[0]).toMatchObject({ statement_id: 'stmt-image', value_id: 'value-image' })

        const warningFilter = wrapper.findAll('.problems-actions nav button').find((button) => button.text().includes('警告'))
        await warningFilter?.trigger('click')
        expect(wrapper.text()).toContain('需要确认重试风险')
        expect(wrapper.text()).not.toContain('图片不能为空')
    })

    it('has an honest empty state and a keyboard-accessible close action', async () => {
        const wrapper = mount(ProgramProblemsPanel)
        expect(wrapper.text()).toContain('当前项目函数没有已知问题')
        await wrapper.get('[aria-label="关闭问题面板"]').trigger('click')
        expect(wrapper.emitted('close')).toHaveLength(1)
    })
})
