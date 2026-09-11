import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import VNextResourceWorkspace from '../components/VNextResourceWorkspace.vue'
import { useVNextStore } from '../store'
import { vnextApi } from '../api'
import type { AssetDefinition } from '../types'

function asset(index: number): AssetDefinition {
    return {
        asset_id: `asset_${index}`, display_name: `图片 ${index}`, category: 'image', folder: '',
        path: `assets/image/${index}.png`, extension: '.png', mime_type: 'image/png', size_bytes: 16,
        width: 10, height: 10, sha256: `${index}`.padStart(64, '0'), source: 'import',
        created_at: '2026-08-27T00:00:00Z', updated_at: '2026-08-27T00:00:00Z', aliases: [], capture: null,
    }
}

describe('VNextResourceWorkspace large library', () => {
    beforeEach(() => { setActivePinia(createPinia()); vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })) })
    afterEach(() => { vi.unstubAllGlobals() })

    it('滚动完整资源目录时只保留视口附近卡片', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        store.assets = Array.from({ length: 300 }, (_, index) => asset(index))
        store.assetCategories = [
            { id: 'image', label: '图像', folders: [] }, { id: 'ocr', label: 'OCR', folders: [] }, { id: 'page', label: '页面', folders: [] },
        ]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockImplementation(async id => `blob:${id}`)
        const wrapper = mount(VNextResourceWorkspace, { attachTo: document.body })
        await vi.waitFor(() => expect(wrapper.findAll('.asset-card').length).toBeGreaterThan(0))
        expect(wrapper.findAll('.asset-card').length).toBeLessThan(60)
        expect(wrapper.text()).toContain('/ 300')

        const grid = wrapper.get('.asset-grid').element as HTMLElement
        Object.defineProperties(grid, {
            scrollTop: { configurable: true, writable: true, value: 8500 },
            clientHeight: { configurable: true, value: 600 },
            clientWidth: { configurable: true, value: 760 },
        })
        await wrapper.get('.asset-grid').trigger('scroll')
        await vi.waitFor(() => expect(wrapper.text()).toContain('图片 299'))
        expect(wrapper.findAll('.asset-card').length).toBeLessThan(60)
        expect(wrapper.text()).not.toContain('图片 0\n')
        wrapper.unmount()
    })

    it('清空搜索后仍定位到当前选中的远端资源', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        store.assets = Array.from({ length: 300 }, (_, index) => asset(index))
        store.assetCategories = [
            { id: 'image', label: '图像', folders: [] }, { id: 'ocr', label: 'OCR', folders: [] }, { id: 'page', label: '页面', folders: [] },
        ]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockImplementation(async id => `blob:${id}`)
        const wrapper = mount(VNextResourceWorkspace, { attachTo: document.body })
        await vi.waitFor(() => expect(wrapper.find('.asset-card').exists()).toBe(true))

        const grid = wrapper.get('.asset-grid').element as HTMLElement
        Object.defineProperties(grid, {
            scrollTop: { configurable: true, writable: true, value: 0 },
            clientHeight: { configurable: true, value: 600 },
            clientWidth: { configurable: true, value: 760 },
        })
        const search = wrapper.get('input[placeholder="搜索资源"]')
        await search.setValue('图片 299')
        await vi.waitFor(() => expect(wrapper.get('.asset-card').text()).toContain('图片 299'))
        await wrapper.get('.asset-card').trigger('click')
        await search.setValue('')

        await vi.waitFor(() => expect(grid.scrollTop).toBeGreaterThan(0))
        await vi.waitFor(() => expect(wrapper.text()).toContain('图片 299'))
        expect(wrapper.findAll('.asset-card').length).toBeLessThan(60)
        wrapper.unmount()
    })

    it('窄窗口选择资源后以抽屉展示检查器，而不是永久隐藏', async () => {
        vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() } as unknown as MediaQueryList))
        const store = useVNextStore()
        store.assets = [asset(1)]
        store.assetCategories = [{ id: 'image', label: '图像', folders: [] }, { id: 'ocr', label: 'OCR', folders: [] }, { id: 'page', label: '页面', folders: [] }]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockResolvedValue('blob:asset_1')
        const wrapper = mount(VNextResourceWorkspace, { attachTo: document.body })
        await vi.waitFor(() => expect(wrapper.find('.asset-card').exists()).toBe(true))

        expect(wrapper.find('.asset-inspector').exists()).toBe(false)
        await wrapper.get('.asset-card').trigger('click')
        expect(wrapper.get('.asset-inspector').classes()).toContain('is-compact')
        expect(wrapper.find('.asset-inspector-scrim').exists()).toBe(true)
        expect(document.activeElement).toBe(wrapper.get('.asset-inspector header button').element)
        await wrapper.get('.asset-inspector').trigger('keydown', { key: 'Escape' })
        await vi.waitFor(() => expect(wrapper.find('.asset-inspector').exists()).toBe(false))
        expect(document.activeElement).toBe(wrapper.get('.asset-card').element)
        wrapper.unmount()
    })

    it('资源接口失败时仍保留三类入口，并提供原位重试', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        const refresh = vi.spyOn(store, 'refreshAssets')
            .mockRejectedValueOnce(new Error('资源注册表被占用'))
            .mockResolvedValueOnce(undefined)
        const wrapper = mount(VNextResourceWorkspace)

        await vi.waitFor(() => expect(wrapper.text()).toContain('资源目录加载失败'))
        const navigation = wrapper.get('.resource-tree nav').text()
        expect(navigation).toContain('图像')
        expect(navigation).toContain('OCR')
        expect(navigation).toContain('页面')
        expect(wrapper.text()).toContain('资源注册表被占用')

        await wrapper.get('.resource-state button').trigger('click')
        await vi.waitFor(() => expect(refresh).toHaveBeenCalledTimes(2))
        expect(wrapper.text()).not.toContain('资源目录加载失败')
        wrapper.unmount()
    })

    it('检查器展示真实捕获溯源字段，且不把工作区冒充运行区域', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        store.assets = [{
            ...asset(1), source: 'capture', capture: {
                platform: 'windows', target_id: 'target_editor', work_area: [10, 20, 800, 600],
                captured_at: '2026-09-01T01:00:00Z', host: 'windows-graphics-capture',
                selection_rect: [30, 40, 120, 80], reference_size: [800, 600], coordinate_space: 'workspace_px',
            },
        }]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockResolvedValue('blob:asset_1')
        vi.spyOn(vnextApi, 'assetReferences').mockResolvedValue({ references: [] })
        const wrapper = mount(VNextResourceWorkspace)
        await vi.waitFor(() => expect(wrapper.find('.asset-card').exists()).toBe(true))

        await wrapper.get('.asset-card').trigger('click')
        const inspector = wrapper.get('.asset-inspector').text()
        expect(inspector).toContain('Capture Session')
        expect(inspector).toContain('捕获选区')
        expect(inspector).toContain('30, 40, 120, 80')
        expect(inspector).toContain('来源工作区')
        expect(inspector).toContain('仅溯源')
        expect(inspector).toContain('target_editor')
        expect(inspector).not.toContain('运行区域')
        wrapper.unmount()
    })

    it('资源元数据与文件夹命名复用紧凑单行字段，反馈留在对应 Control 下方', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        store.assets = [asset(1)]
        store.assetCategories = [
            { id: 'image', label: '图像', folders: [] }, { id: 'ocr', label: 'OCR', folders: [] }, { id: 'page', label: '页面', folders: [] },
        ]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockResolvedValue('blob:asset_1')
        vi.spyOn(vnextApi, 'assetReferences').mockResolvedValue({ references: [] })
        const wrapper = mount(VNextResourceWorkspace)
        await vi.waitFor(() => expect(wrapper.find('.asset-card').exists()).toBe(true))

        await wrapper.get('.asset-card').trigger('click')
        const metadataRows = wrapper.findAll('.asset-field.app-form-row')
        expect(metadataRows).toHaveLength(3)
        expect(metadataRows.every(row => row.find('.app-form-label').exists() && row.find('.app-form-control').exists())).toBe(true)

        const folderRow = wrapper.get('.folder-field.app-form-row')
        expect(folderRow.get('input').attributes('aria-describedby')).toBe('folder-dialog-feedback')
        expect(folderRow.get('.app-form-help').text()).toContain('/assets/image/')
        expect(wrapper.get('.folder-dialog footer button[type="submit"]').attributes('disabled')).toBeDefined()
        wrapper.unmount()
    })

    it('导入入口尊重最终分类，并提示同内容资源仍作为独立项保留', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        store.assets = [asset(1)]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockImplementation(async id => `blob:${id}`)
        vi.spyOn(vnextApi, 'assetReferences').mockResolvedValue({ references: [] })
        const importAsset = vi.spyOn(store, 'importAsset').mockImplementation(async (_file, category, folder) => {
            const imported: AssetDefinition = { ...asset(2), category, folder: folder || '', display_name: '副本' }
            store.assets = [...store.assets, imported]
            return { asset: imported, duplicate_of: asset(1), transaction_id: 'tx_import' } as never
        })
        const wrapper = mount(VNextResourceWorkspace, { props: { initialCategory: 'page' } })
        await vi.waitFor(() => expect(wrapper.text()).toContain('这里还没有资源'))

        const input = wrapper.get('input[type="file"][multiple]').element as HTMLInputElement
        Object.defineProperty(input, 'files', { configurable: true, value: [new File(['png'], 'copy.png', { type: 'image/png' })] })
        await wrapper.get('input[type="file"][multiple]').trigger('change')

        await vi.waitFor(() => expect(importAsset).toHaveBeenCalledWith(expect.any(File), 'page', ''))
        await vi.waitFor(() => expect(wrapper.text()).toContain('按独立资源保留'))
        expect(wrapper.get('.asset-card').text()).toContain('副本')
        wrapper.unmount()
    })

    it('从当前三类目录发起独立视觉录入，并在会话未结束时禁用重复入口', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        store.assetCategories = [
            { id: 'image', label: '图像', folders: [] },
            { id: 'ocr', label: 'OCR', folders: [] },
            { id: 'page', label: '页面', folders: [] },
        ]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        const wrapper = mount(VNextResourceWorkspace)
        await vi.waitFor(() => expect(wrapper.find('.capture-action').exists()).toBe(true))

        const ocrRoot = wrapper.findAll('.resource-tree nav > button').find(button => button.text().includes('OCR'))
        if (!ocrRoot) throw new Error('expected OCR resource root')
        await ocrRoot.trigger('click')
        await wrapper.get('.capture-action').trigger('click')

        const request = wrapper.emitted('capture-resource')?.[0]
        expect(request?.[0]).toBe('ocr')
        expect(request?.[1]).toBeInstanceOf(HTMLElement)
        await wrapper.setProps({ captureBusy: true })
        expect(wrapper.get('.capture-action').attributes('disabled')).toBeDefined()
        expect(wrapper.get('.capture-action').attributes('aria-busy')).toBe('true')
        wrapper.unmount()
    })

    it('参数选择模式明确保持选中态，并只在确认后提交资源', async () => {
        const store = useVNextStore()
        store.assets = [asset(1)]
        store.assetCategories = [{ id: 'image', label: '图像', folders: [] }, { id: 'ocr', label: 'OCR', folders: [] }, { id: 'page', label: '页面', folders: [] }]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockResolvedValue('blob:asset_1')
        const wrapper = mount(VNextResourceWorkspace, { props: { selectionMode: true, selectionLabel: '应用到“图片”' } })
        await vi.waitFor(() => expect(wrapper.find('.asset-card').exists()).toBe(true))

        await wrapper.get('.asset-card').trigger('click')
        expect(wrapper.get('.asset-card').classes()).toContain('active')
        expect(wrapper.get('.asset-card').attributes('aria-pressed')).toBe('true')
        expect(wrapper.emitted('insert-reference')).toBeUndefined()
        await wrapper.get('.selection-action').trigger('click')
        expect(wrapper.emitted('insert-reference')?.[0]?.[0]).toMatchObject({ asset_id: 'asset_1' })
        wrapper.unmount()
    })

    it('参数选择可显式取消，且普通浏览模式不显示无承接的插入入口', async () => {
        const store = useVNextStore()
        store.assets = [asset(1)]
        store.assetCategories = [{ id: 'image', label: '图像', folders: [] }, { id: 'ocr', label: 'OCR', folders: [] }, { id: 'page', label: '页面', folders: [] }]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockResolvedValue('blob:asset_1')

        const selection = mount(VNextResourceWorkspace, { props: { selectionMode: true } })
        await vi.waitFor(() => expect(selection.find('.selection-cancel').exists()).toBe(true))
        await selection.get('.selection-cancel').trigger('click')
        expect(selection.emitted('cancel-selection')).toHaveLength(1)
        expect(selection.emitted('insert-reference')).toBeUndefined()
        selection.unmount()

        const browsing = mount(VNextResourceWorkspace)
        await vi.waitFor(() => expect(browsing.find('.asset-card').exists()).toBe(true))
        await browsing.get('.asset-card').trigger('click')
        expect(browsing.text()).not.toContain('插入引用')
        browsing.unmount()
    })

    it('存在 ProgramDocument 引用时阻止删除且不显示伪造的强制清理', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        store.assets = [asset(1)]
        store.functions = [{
            function_id: 'official.image.find', namespace: '图像', name: '查找', qualified_name: '图像.查找',
            label: '图像.查找', category: '图像', return_type: 'optional<image_match>', description: '',
            platforms: ['windows'], capabilities: [], opcode: 'vision.find',
            parameters: [{
                parameter_id: 'official.image.find.parameter.image', name: 'image', display_name: '图片',
                value_type: 'asset_ref<image>', required: true, default: null, description: '',
            }],
        }]
        store.assetCategories = [{ id: 'image', label: '图像', folders: [] }, { id: 'ocr', label: 'OCR', folders: [] }, { id: 'page', label: '页面', folders: [] }]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockResolvedValue('blob:asset_1')
        const deleteAsset = vi.spyOn(store, 'deleteAsset')
        vi.spyOn(vnextApi, 'assetReferences').mockResolvedValue({ references: [{
            kind: 'program_parameter', path: 'program/functions/function_main.json',
            function_id: 'function_main', statement_id: 'statement_find',
            parameter_id: 'official.image.find.parameter.image', value_id: 'value_image',
            preview: 'official.image.find · official.image.find.parameter.image',
        }] })
        const wrapper = mount(VNextResourceWorkspace)
        await vi.waitFor(() => expect(wrapper.find('.asset-card').exists()).toBe(true))

        await wrapper.get('.asset-card').trigger('click')
        await vi.waitFor(() => expect(wrapper.get('.reference-list').text()).toContain('图像.查找 · 图片'))
        expect(wrapper.get('.reference-list').text()).not.toContain('official.image.find.parameter.image')
        await wrapper.get('.asset-actions .danger').trigger('click')
        expect(deleteAsset).not.toHaveBeenCalled()
        await vi.waitFor(() => expect(wrapper.text()).toContain('系统不会生成无效脚本'))
        expect(wrapper.text()).not.toContain('确认删除并清理引用')
        wrapper.unmount()
    })

    it('未引用资源需要二次确认后才真正删除', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        store.assets = [asset(1)]
        store.assetCategories = [{ id: 'image', label: '图像', folders: [] }, { id: 'ocr', label: 'OCR', folders: [] }, { id: 'page', label: '页面', folders: [] }]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockResolvedValue('blob:asset_1')
        const deleteAsset = vi.spyOn(store, 'deleteAsset').mockResolvedValue({ deleted: true })
        vi.spyOn(vnextApi, 'assetReferences').mockResolvedValue({ references: [] })
        const wrapper = mount(VNextResourceWorkspace)
        await vi.waitFor(() => expect(wrapper.find('.asset-card').exists()).toBe(true))

        await wrapper.get('.asset-card').trigger('click')
        await wrapper.get('.asset-actions .danger').trigger('click')
        expect(deleteAsset).not.toHaveBeenCalled()
        await vi.waitFor(() => expect(wrapper.text()).toContain('删除后无法从项目内恢复'))
        await wrapper.get('.asset-actions .solid').trigger('click')
        expect(deleteAsset).toHaveBeenCalledWith('asset_1')
        wrapper.unmount()
    })

    it('键盘删除后选择并聚焦相邻资源', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        store.assets = [asset(1), asset(2)]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockImplementation(async id => `blob:${id}`)
        vi.spyOn(vnextApi, 'assetReferences').mockResolvedValue({ references: [] })
        vi.spyOn(store, 'deleteAsset').mockImplementation(async id => {
            store.assets = store.assets.filter(item => item.asset_id !== id)
            return { deleted: true }
        })
        const wrapper = mount(VNextResourceWorkspace, { attachTo: document.body })
        await vi.waitFor(() => expect(wrapper.findAll('.asset-card')).toHaveLength(2))

        await wrapper.findAll('.asset-card')[0].trigger('click')
        await wrapper.get('.asset-actions .danger').trigger('click')
        await vi.waitFor(() => expect(wrapper.find('.asset-actions .solid').exists()).toBe(true))
        await wrapper.get('.asset-actions .solid').trigger('click')

        await vi.waitFor(() => expect(wrapper.findAll('.asset-card')).toHaveLength(1))
        expect(wrapper.get('.asset-card').attributes('aria-pressed')).toBe('true')
        await vi.waitFor(() => expect(document.activeElement).toBe(wrapper.get('.asset-card').element))
        wrapper.unmount()
    })

    it('修改分类或子目录后自动导航到新位置并保留选中态', async () => {
        const store = useVNextStore()
        store.workspace = { workspace_id: 'w', generation: 1, project_id: 'p', project_name: '演示项目', project_path: 'D:/Demo', read_only: false }
        store.assets = [asset(1)]
        store.assetCategories = [
            { id: 'image', label: '图像', folders: [] },
            { id: 'ocr', label: 'OCR', folders: ['登录'] },
            { id: 'page', label: '页面', folders: [] },
        ]
        vi.spyOn(store, 'refreshAssets').mockResolvedValue(undefined)
        vi.spyOn(store, 'assetPreviewUrl').mockResolvedValue('blob:asset_1')
        vi.spyOn(store, 'updateAsset').mockImplementation(async (_id, payload) => {
            const updated = { ...store.assets[0], ...payload, updated_at: '2026-08-27T01:00:00Z' } as AssetDefinition
            store.assets = [updated]
            return updated
        })
        const wrapper = mount(VNextResourceWorkspace)
        await vi.waitFor(() => expect(wrapper.find('.asset-card').exists()).toBe(true))

        await wrapper.get('.asset-card').trigger('click')
        const selects = wrapper.findAll('.asset-details select')
        await selects[0].setValue('ocr')
        const folderInput = wrapper.findAll('.asset-details input')[1]
        await folderInput.setValue('登录')
        await folderInput.trigger('blur')

        await vi.waitFor(() => {
            expect(wrapper.get('.gallery-header').text()).toContain('OCR')
            expect(wrapper.get('.gallery-header').text()).toContain('登录')
            expect(wrapper.get('.asset-card').classes()).toContain('active')
            expect(wrapper.get('.asset-card').text()).toContain('图片 1')
        })
        wrapper.unmount()
    })
})
