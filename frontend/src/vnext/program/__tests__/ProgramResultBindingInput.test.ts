import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ProgramResultBindingInput from '../ProgramResultBindingInput.vue'

const locals = [
    { source: 'local' as const, id: 'local_text', display_name: '登录结果', value_type: 'string' },
    { source: 'local' as const, id: 'local_count', display_name: '次数', value_type: 'int64' },
]

describe('ProgramResultBindingInput', () => {
    it('uses one field for no result, a new local, and an existing local', async () => {
        const wrapper = mount(ProgramResultBindingInput, { props: { statementId: 'stmt_1', compatibleLocals: locals } })
        const input = wrapper.get('input')
        expect(input.attributes('placeholder')).toContain('留空不保存')
        await input.setValue('截图结果')
        await input.trigger('keydown.enter')
        expect(wrapper.emitted('commit')?.at(-1)).toEqual([{ kind: 'new_local', display_name: '截图结果' }])
        await input.trigger('focus')
        await input.setValue('@登录')
        expect(wrapper.text()).toContain('使用已有局部变量')
        expect(wrapper.text()).toContain('登录结果')
        expect(wrapper.text()).not.toContain('次数')
        await wrapper.get('.result-binding-suggestions button').trigger('click')
        expect(wrapper.emitted('commit')?.at(-1)).toEqual([{
            kind: 'existing_local', symbol_id: 'local_text', display_name: '登录结果', value_type: 'string',
        }])
        await input.setValue('')
        await input.trigger('keydown.enter')
        expect(wrapper.emitted('commit')?.at(-1)).toEqual([null])
    })

    it('does not turn an unknown reference-like draft into a new variable', async () => {
        const wrapper = mount(ProgramResultBindingInput, { props: { statementId: 'stmt_2', compatibleLocals: locals } })
        const input = wrapper.get('input')
        await input.setValue('[局部 · 不存在]')
        await input.trigger('keydown.enter')
        expect(wrapper.text()).toContain('请从列表选择一个已有局部变量')
        expect(wrapper.emitted('commit')).toBeUndefined()
    })
})
