import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import ProgramInlineQuickInsert from '../ProgramInlineQuickInsert.vue'
import type { FunctionCatalogCandidate } from '../functionCatalogSearch'

const candidates: FunctionCatalogCandidate[] = [
    {
        key: 'official:official.control.click',
        selection: { source: 'official', function_id: 'official.control.click' },
        label: '点击控件', namespace: '控件', sourceLabel: '官方', description: '控件.点击',
        parts: [{ text: '点击' }, { text: '控件', dynamic: true }], searchTerms: ['控件', '点击', 'control'],
    },
    {
        key: 'structure:if', selection: { source: 'structure', function_id: 'if' },
        label: '如果条件', namespace: '流程控制', sourceLabel: '结构', description: '条件成立时执行',
        parts: [{ text: '如果' }, { text: '条件', dynamic: true }], searchTerms: ['如果', '条件', '判断'],
    },
]

describe('ProgramInlineQuickInsert', () => {
    it('focuses immediately and inserts the active local-search result with the keyboard', async () => {
        const insert = vi.fn().mockResolvedValue(undefined)
        const wrapper = mount(ProgramInlineQuickInsert, { attachTo: document.body, props: { candidates, insert } })
        await nextTick()
        const input = wrapper.get<HTMLInputElement>('input')
        expect(document.activeElement).toBe(input.element)

        await input.setValue('控件')
        await input.trigger('keydown', { key: 'Enter' })
        await flushPromises()
        expect(insert).toHaveBeenCalledWith({ source: 'official', function_id: 'official.control.click' })
        expect(wrapper.emitted('complete')?.[0]?.[0]).toEqual({ source: 'official', function_id: 'official.control.click' })
        wrapper.unmount()
    })

    it('does not insert during IME composition and cancels without mutation', async () => {
        const insert = vi.fn().mockResolvedValue(undefined)
        const wrapper = mount(ProgramInlineQuickInsert, { props: { candidates, insert } })
        const input = wrapper.get('input')
        await input.trigger('compositionstart')
        await input.trigger('keydown', { key: 'Enter', isComposing: true })
        expect(insert).not.toHaveBeenCalled()
        await input.trigger('compositionend')
        await input.trigger('keydown', { key: 'Escape' })
        expect(wrapper.emitted('cancel')).toHaveLength(1)
        expect(insert).not.toHaveBeenCalled()
    })

    it('keeps the query and anchor UI available after a failed insert', async () => {
        const insert = vi.fn().mockRejectedValue(new Error('保存冲突，请重试'))
        const wrapper = mount(ProgramInlineQuickInsert, { props: { candidates, insert } })
        const input = wrapper.get('input')
        await input.setValue('控件')
        await input.trigger('keydown', { key: 'Enter' })
        await flushPromises()
        expect(wrapper.get('input').element.value).toBe('控件')
        expect(wrapper.get('[role="alert"]').text()).toBe('保存冲突，请重试')
        expect(wrapper.emitted('complete')).toBeUndefined()
    })

    it('hands an unmatched query to the complete library instead of inventing another catalog', async () => {
        const wrapper = mount(ProgramInlineQuickInsert, { props: { candidates, insert: vi.fn() } })
        await wrapper.get('input').setValue('完全不存在')
        await wrapper.get('.quick-insert__empty button').trigger('click')
        expect(wrapper.emitted('requestLibrary')?.[0]).toEqual(['完全不存在'])
    })
})
