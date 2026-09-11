import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ProgramFunctionSignatureDialog from '../ProgramFunctionSignatureDialog.vue'
import type { ProgramSummaryDto } from '../serverTypes'

function program(): ProgramSummaryDto {
    return {
        document_id: 'document-battle', function_id: 'function-battle', display_name: '战斗-刷图',
        statement_count: 12, revision: 'revision-a', contract_version: '1', contract_fingerprint: 'fingerprint-a',
        return_type: 'bool',
        parameters: [{
            parameter_id: 'parameter-max-battles', symbol_id: 'symbol-max-battles', display_name: '最大战斗次数',
            value_type: 'int64', required: false,
            default_value: { value_id: 'value-default-max-battles', kind: 'int64', value: 20 },
        }],
    }
}

describe('ProgramFunctionSignatureDialog', () => {
    it('edits parameter contracts without exposing stable ids as user input', async () => {
        const wrapper = mount(ProgramFunctionSignatureDialog, {
            props: { open: true, program: program() },
            global: { stubs: { Teleport: true } },
        })

        expect(wrapper.text()).toContain('参数与返回值')
        expect((wrapper.get('input[placeholder="例如：最大战斗次数"]').element as HTMLInputElement).value).toBe('最大战斗次数')
        expect(wrapper.find('input[value="parameter-max-battles"]').exists()).toBe(false)

        await wrapper.get('input[placeholder="例如：最大战斗次数"]').setValue('本次最多战斗')
        await wrapper.get('form').trigger('submit')
        await flushPromises()

        expect(wrapper.emitted('save')?.[0]?.[0]).toMatchObject({
            parameters: [{ parameter_id: 'parameter-max-battles', display_name: '本次最多战斗', value_type: 'int64', required: false }],
            returnType: 'bool',
        })
        wrapper.unmount()
    })

    it('adds, reorders and validates parameter names before saving', async () => {
        const wrapper = mount(ProgramFunctionSignatureDialog, {
            props: { open: true, program: program() },
            global: { stubs: { Teleport: true } },
        })
        await wrapper.findAll('button').find((button) => button.text().includes('添加参数'))!.trigger('click')
        expect(wrapper.findAll('.parameter-card')).toHaveLength(2)

        const names = wrapper.findAll('input[placeholder="例如：最大战斗次数"]')
        await names[1].setValue('最大战斗次数')
        await wrapper.get('form').trigger('submit')
        expect(wrapper.text()).toContain('参数名称不能重复')
        expect(wrapper.emitted('save')).toBeUndefined()
        wrapper.unmount()
    })
})
