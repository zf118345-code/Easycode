import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import VNextWelcome from '../components/VNextWelcome.vue'
import { useVNextStore } from '../store'

describe('VNextWelcome project entry', () => {
    beforeEach(() => {
        localStorage.clear()
        setActivePinia(createPinia())
    })

    it('只提供打开、新建和可真实打开的最近项目', async () => {
        localStorage.setItem('easycode.vnext.recent-projects', JSON.stringify([{ name: '测试项目', path: 'D:/Projects/Test' }]))
        const store = useVNextStore()
        const open = vi.spyOn(store, 'openProject').mockResolvedValue({
            workspace: { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '测试项目', project_path: 'D:/Projects/Test', read_only: false },
        } as never)
        const wrapper = mount(VNextWelcome)

        expect(wrapper.text()).toContain('打开项目')
        expect(wrapper.text()).toContain('新建项目')
        expect(wrapper.text()).toContain('最近项目')
        expect(wrapper.find('input#project-path').exists()).toBe(false)

        await wrapper.find('.recent-list button').trigger('click')
        expect(open).toHaveBeenCalledWith('D:/Projects/Test')

        await wrapper.findAll('.welcome-actions .vnext-button')[1].trigger('click')
        expect(wrapper.find('input#vnext-project-path').exists()).toBe(true)
    })
})
