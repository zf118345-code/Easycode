import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import VNextCreateProjectDialog from '../components/VNextCreateProjectDialog.vue'
import { useVNextStore } from '../store'

describe('VNextCreateProjectDialog', () => {
    beforeEach(() => { setActivePinia(createPinia()) })

    it('keeps path entry and folder selection in one compact field row', async () => {
        const store = useVNextStore()
        vi.spyOn(store, 'chooseFolder').mockResolvedValue('D:/Projects/每日任务')
        const wrapper = mount(VNextCreateProjectDialog, { props: { open: true } })

        const row = wrapper.get('.project-path-row.app-form-row')
        const input = row.get<HTMLInputElement>('.app-form-control')
        const action = row.get<HTMLButtonElement>('.app-field-action')
        expect(input.element.parentElement).toBe(action.element.parentElement)
        expect(action.attributes('aria-label')).toBe('选择文件夹')

        await action.trigger('click')
        await flushPromises()
        expect(input.element.value).toBe('D:/Projects/每日任务')
        expect(row.get('.app-form-help').text()).toContain('每日任务')
        expect(input.attributes('aria-describedby')).toBe('create-project-preview')
    })
})
