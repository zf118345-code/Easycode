import { defineComponent, h } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import VNextAsyncWorkspaceHost from '../components/VNextAsyncWorkspaceHost.vue'

/* eslint-disable vue/one-component-per-file -- focused test fixtures intentionally stay beside their loader assertions */

describe('VNextAsyncWorkspaceHost', () => {
    beforeEach(() => {
        vi.restoreAllMocks()
    })

    it('shows an in-place loading state and forwards attributes and events after loading', async () => {
        let resolveModule!: (value: { default: ReturnType<typeof defineComponent> }) => void
        const loader = vi.fn(() => new Promise<{ default: ReturnType<typeof defineComponent> }>((resolve) => { resolveModule = resolve }))
        const Workspace = defineComponent({
            inheritAttrs: false,
            setup(_, { attrs }) {
                return () => h('button', { class: attrs.class, onClick: attrs.onDone as () => void }, '工作区就绪')
            },
        })
        const done = vi.fn()
        const wrapper = mount(VNextAsyncWorkspaceHost, {
            props: { label: '异步测试工作区', loader },
            attrs: { class: 'workspace-class', onDone: done },
        })

        expect(wrapper.text()).toContain('正在打开异步测试工作区')
        expect(wrapper.get('[role="status"]').attributes('aria-busy')).toBe('true')

        resolveModule({ default: Workspace })
        await flushPromises()
        expect(wrapper.get('.workspace-class').text()).toBe('工作区就绪')
        await wrapper.get('.workspace-class').trigger('click')
        expect(done).toHaveBeenCalledTimes(1)
    })

    it('keeps the shell usable after a load failure and retries only that workspace', async () => {
        const Workspace = defineComponent({ setup: () => () => h('div', { class: 'retry-ready' }, '已恢复') })
        const loader = vi.fn()
            .mockRejectedValueOnce(new Error('测试分块不可用'))
            .mockResolvedValueOnce({ default: Workspace })
        const wrapper = mount(VNextAsyncWorkspaceHost, { props: { label: '运行记录', loader } })
        await flushPromises()

        expect(wrapper.get('[role="alert"]').text()).toContain('测试分块不可用')
        expect(wrapper.text()).toContain('重新加载')
        await wrapper.get('button').trigger('click')
        await flushPromises()

        expect(wrapper.get('.retry-ready').text()).toBe('已恢复')
        expect(loader).toHaveBeenCalledTimes(2)
    })
})
