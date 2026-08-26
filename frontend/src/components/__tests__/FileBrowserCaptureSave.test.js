import { describe, beforeEach, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ElementPlus from 'element-plus'

import FileBrowser from '../FileBrowser.vue'
import { visionApi } from '@/api/visionApi'
import { useUiStore } from '@/stores/uiStore'
import { ElMessageBox } from 'element-plus'

vi.mock('@/api/visionApi', () => ({
    visionApi: {
        createTemplateFolder: vi.fn().mockResolvedValue({}),
        getTemplatesTree: vi.fn().mockResolvedValue({ tree: [] }),
        getTemplatePreview: vi.fn().mockResolvedValue({ images: [] }),
        registerTemplate: vi.fn(),
        getTemplateImpact: vi.fn(),
        deleteTemplateEntry: vi.fn(),
        moveTemplateEntry: vi.fn()
    }
}))

globalThis.ResizeObserver = globalThis.ResizeObserver || class {
    observe() {}
    unobserve() {}
    disconnect() {}
}

describe('FileBrowser capture-save mode', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        visionApi.createTemplateFolder.mockResolvedValue({})
        visionApi.getTemplatesTree.mockResolvedValue({ tree: [] })
        visionApi.getTemplatePreview.mockResolvedValue({ images: [] })
        visionApi.registerTemplate.mockResolvedValue({ asset_ref: 'asset://asset_registered' })
        visionApi.getTemplateImpact.mockResolvedValue({
            path: 'image/login.png', file_count: 1, asset_count: 1,
            node_count: 0, reference_count: 0, references: [], protected: false
        })
        visionApi.deleteTemplateEntry.mockResolvedValue({
            operation: 'delete', path: 'image/login.png', node_count: 0,
            reference_count: 0, trash_id: 'trash_test'
        })
    })

    it('复用当前目录选择，并允许空名称交给捕获事务自动命名', async () => {
        const pinia = createPinia()
        setActivePinia(pinia)
        useUiStore().canvasMode = 'topology'

        const wrapper = mount(FileBrowser, {
            props: {
                projectPath: 'D:/projects/demo',
                mode: 'capture-save',
                initialPath: 'image',
                allowEmptyName: true,
                saveButtonText: '录入图片'
            },
            global: { plugins: [pinia, ElementPlus] }
        })
        await flushPromises()

        expect(visionApi.getTemplatePreview).toHaveBeenLastCalledWith('D:/projects/demo', 'image')
        expect(wrapper.text()).toContain('/templates/image')
        expect(wrapper.text()).toContain('image')
        expect(wrapper.text()).toContain('ocr')
        expect(wrapper.text()).toContain('page')
        expect(wrapper.text()).not.toContain('拓扑资产模式')
        const topLevelFolders = wrapper.findAll('.tree-wrapper > .el-tree > .el-tree-node')
        expect(topLevelFolders).toHaveLength(3)
        expect(topLevelFolders.map(node => node.text())).toEqual(expect.arrayContaining([
            expect.stringContaining('image'),
            expect.stringContaining('ocr'),
            expect.stringContaining('page')
        ]))

        const saveButton = wrapper.findAll('button').find(button => button.text().includes('录入图片'))
        await saveButton.trigger('click')

        expect(wrapper.emitted('save')).toEqual([[{ relativePath: 'image', fileName: '' }]])
        wrapper.unmount()
    })

    it('保存按钮跟随真实事务 busy，慢保存期间不会重复提交', async () => {
        const pinia = createPinia()
        setActivePinia(pinia)
        const wrapper = mount(FileBrowser, {
            props: {
                projectPath: 'D:/projects/demo',
                mode: 'capture-save',
                initialPath: 'image',
                allowEmptyName: true
            },
            global: { plugins: [pinia, ElementPlus] }
        })
        await flushPromises()

        const saveButton = wrapper.findAll('button').find(button => button.text().includes('保存截图'))
        await saveButton.trigger('click')
        await wrapper.setProps({ saveBusy: true })
        await saveButton.trigger('click')
        expect(wrapper.emitted('save')).toHaveLength(1)
        expect(saveButton.attributes('disabled')).toBeDefined()

        await wrapper.setProps({ saveBusy: false })
        await saveButton.trigger('click')
        expect(wrapper.emitted('save')).toHaveLength(2)
        wrapper.unmount()
    })

    it('初始目录只负责默认选中，捕获保存时可以切换到其他用途目录', async () => {
        const pinia = createPinia()
        setActivePinia(pinia)
        const wrapper = mount(FileBrowser, {
            props: {
                projectPath: 'D:/projects/demo',
                mode: 'capture-save',
                initialPath: 'image',
                allowEmptyName: true
            },
            global: { plugins: [pinia, ElementPlus] }
        })
        await flushPromises()

        const ocrFolder = wrapper.findAll('.el-tree-node__content')
            .find(item => item.text().trim().startsWith('ocr'))
        expect(ocrFolder).toBeTruthy()
        await ocrFolder.trigger('click')
        await flushPromises()

        expect(visionApi.getTemplatePreview).toHaveBeenLastCalledWith('D:/projects/demo', 'ocr')
        expect(wrapper.text()).toContain('/templates/ocr')
        const saveButton = wrapper.findAll('button').find(button => button.text().includes('保存截图'))
        await saveButton.trigger('click')
        expect(wrapper.emitted('save')).toEqual([[{ relativePath: 'ocr', fileName: '' }]])
        wrapper.unmount()
    })

    it('目录接口失败时仍保留三个用途根目录，不显示 No Data', async () => {
        visionApi.getTemplatesTree.mockRejectedValueOnce(new Error('缺少当前工作区身份'))
        const pinia = createPinia()
        setActivePinia(pinia)
        const wrapper = mount(FileBrowser, {
            props: {
                projectPath: 'D:/projects/demo',
                mode: 'capture-save',
                initialPath: 'image',
                allowEmptyName: true
            },
            global: { plugins: [pinia, ElementPlus] }
        })
        await flushPromises()

        const topLevelFolders = wrapper.findAll('.tree-wrapper > .el-tree > .el-tree-node')
        expect(topLevelFolders).toHaveLength(3)
        expect(wrapper.text()).toContain('image')
        expect(wrapper.text()).toContain('ocr')
        expect(wrapper.text()).toContain('page')
        expect(wrapper.text()).not.toContain('No Data')
        wrapper.unmount()
    })

    it('选择已注册图片时返回稳定 asset 引用，不受画布模式影响', async () => {
        visionApi.getTemplatePreview.mockResolvedValue({
            images: [{
                name: 'login.png',
                relative_path: 'page/login.png',
                asset_ref: 'asset://asset_login',
                kind: 'page'
            }]
        })
        const pinia = createPinia()
        setActivePinia(pinia)
        useUiStore().canvasMode = 'topology'

        const wrapper = mount(FileBrowser, {
            props: {
                projectPath: 'D:/projects/demo',
                mode: 'select',
                initialPath: 'page',
            },
            global: { plugins: [pinia, ElementPlus] }
        })
        await flushPromises()

        await wrapper.find('.image-card').trigger('click')
        const confirmButton = wrapper.findAll('button').find(button => button.text().includes('确定选择'))
        await confirmButton.trigger('click')
        await flushPromises()

        expect(wrapper.emitted('select')).toEqual([['asset://asset_login']])
        expect(visionApi.getTemplatePreview).toHaveBeenLastCalledWith('D:/projects/demo', 'page')
        expect(wrapper.text()).not.toContain('topology_assets')
        wrapper.unmount()
    })

    it('图片卡片支持键盘选择并再次确认', async () => {
        visionApi.getTemplatePreview.mockResolvedValue({
            images: [{
                name: 'login.png', relative_path: 'image/login.png',
                asset_ref: 'asset://asset_login', kind: 'image'
            }]
        })
        const pinia = createPinia()
        setActivePinia(pinia)
        const wrapper = mount(FileBrowser, {
            props: { projectPath: 'D:/projects/demo', mode: 'select', initialPath: 'image' },
            global: { plugins: [pinia, ElementPlus] }
        })
        await flushPromises()

        const card = wrapper.find('.image-card')
        expect(card.attributes('role')).toBe('option')
        expect(card.attributes('tabindex')).toBe('0')
        await card.trigger('keydown', { key: 'Enter' })
        expect(card.attributes('aria-selected')).toBe('true')
        await card.trigger('keydown', { key: 'Enter' })
        await flushPromises()

        expect(wrapper.emitted('select')).toEqual([['asset://asset_login']])
        wrapper.unmount()
    })

    it('删除图片前展示影响确认，并通过受控资源接口删除', async () => {
        visionApi.getTemplatePreview.mockResolvedValue({
            images: [{
                name: 'login.png', relative_path: 'image/login.png',
                asset_ref: 'asset://asset_login', kind: 'image'
            }]
        })
        const confirm = vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue('confirm')
        const pinia = createPinia()
        setActivePinia(pinia)
        const wrapper = mount(FileBrowser, {
            props: { projectPath: 'D:/projects/demo', mode: 'select', initialPath: 'image' },
            global: { plugins: [pinia, ElementPlus] }
        })
        await flushPromises()

        await wrapper.find('.image-actions .el-button--danger').trigger('click')
        await flushPromises()

        expect(visionApi.getTemplateImpact).toHaveBeenCalledWith('D:/projects/demo', 'image/login.png')
        expect(confirm).toHaveBeenCalled()
        expect(visionApi.deleteTemplateEntry).toHaveBeenCalledWith('D:/projects/demo', 'image/login.png')
        expect(wrapper.emitted('mutated')?.[0]?.[0]).toMatchObject({ operation: 'delete', trash_id: 'trash_test' })
        confirm.mockRestore()
        wrapper.unmount()
    })
})
