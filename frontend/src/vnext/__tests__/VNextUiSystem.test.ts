import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import VNextPaneHeader from '../components/ui/VNextPaneHeader.vue'
import VNextWorkspaceState from '../components/ui/VNextWorkspaceState.vue'
import VNextInlineNotice from '../components/ui/VNextInlineNotice.vue'

describe('VNext UI system primitives', () => {
    it('keeps pane identity, metadata and actions in one semantic header', () => {
        const wrapper = mount(VNextPaneHeader, {
            props: { title: '资源', meta: '12 项', role: 'workspace', headingLevel: 1 },
            slots: { actions: '<button type="button">导入</button>' },
        })

        expect(wrapper.attributes('data-ui-role')).toBe('workspace')
        expect(wrapper.get('h1').text()).toBe('资源')
        expect(wrapper.get('.vnext-pane-header__meta').text()).toBe('12 项')
        expect(wrapper.get('.vnext-pane-header__actions button').text()).toBe('导入')
    })

    it('keeps grouped header actions inside the same shared action owner', () => {
        const wrapper = mount(VNextPaneHeader, {
            props: { title: '资源', meta: 1 },
            slots: { actions: '<span class="domain-action-group"><button type="button">新建</button><button type="button">导入</button></span>' },
        })

        expect(wrapper.findAll('.vnext-pane-header__actions button')).toHaveLength(2)
        expect(wrapper.get('.domain-action-group').element.parentElement?.classList).toContain('vnext-pane-header__actions')
    })

    it('owns loading and error announcements without changing page topology', () => {
        const loading = mount(VNextWorkspaceState, { props: { kind: 'loading', title: '正在载入' } })
        const failure = mount(VNextWorkspaceState, { props: { kind: 'error', title: '载入失败', description: '请重试' } })

        expect(loading.attributes('role')).toBe('status')
        expect(loading.attributes('data-ui-state')).toBe('loading')
        expect(failure.attributes('role')).toBe('alert')
        expect(failure.attributes('aria-live')).toBe('assertive')
        expect(failure.text()).toContain('请重试')
    })

    it('uses one feedback contract for success and recoverable errors', async () => {
        const wrapper = mount(VNextInlineNotice, { props: { tone: 'success', message: '已保存', dismissible: true } })
        expect(wrapper.attributes('role')).toBe('status')
        expect(wrapper.attributes('data-ui-feedback')).toBe('success')
        await wrapper.get('button[aria-label="关闭提示"]').trigger('click')
        expect(wrapper.emitted('dismiss')).toHaveLength(1)

        await wrapper.setProps({ tone: 'error', message: '保存失败' })
        expect(wrapper.attributes('role')).toBe('alert')
        expect(wrapper.attributes('aria-live')).toBe('assertive')
    })
})
