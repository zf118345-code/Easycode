import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import CaptureFileManagerView from '@/views/CaptureFileManagerView.vue'
import { captureApi } from '@/api/captureApi'
import { visionApi } from '@/api/visionApi'
import { getWorkspaceIdentity, setWorkspaceIdentity } from '@/api/workspaceIdentity'

vi.mock('@/api/captureApi', () => ({
    captureApi: {
        getSnapshot: vi.fn(),
        saveAssets: vi.fn(),
        requestAction: vi.fn(),
        undoAssets: vi.fn()
    }
}))

vi.mock('@/api/visionApi', () => ({
    visionApi: {
        getTemplatesTree: vi.fn(),
        getTemplatePreview: vi.fn(),
        getImageThumb: vi.fn(),
        createTemplateFolder: vi.fn(),
        getTemplateImpact: vi.fn(),
        deleteTemplateEntry: vi.fn(),
        moveTemplateEntry: vi.fn(),
        listTemplateTrash: vi.fn(),
        restoreTemplateEntry: vi.fn(),
        registerTemplate: vi.fn()
    }
}))

globalThis.ResizeObserver = globalThis.ResizeObserver || class {
    observe() {}
    unobserve() {}
    disconnect() {}
}

describe('捕获后的桌面资源管理器完整入口', () => {
    let messageHandler

    beforeEach(() => {
        vi.clearAllMocks()
        setWorkspaceIdentity(null)
        messageHandler = null
        Object.defineProperty(window, 'chrome', {
            configurable: true,
            writable: true,
            value: {
                webview: {
                    postMessage: vi.fn(),
                    addEventListener: vi.fn((type, handler) => {
                        if (type === 'message') messageHandler = handler
                    }),
                    removeEventListener: vi.fn()
                }
            }
        })
        window.history.replaceState({}, '', '/')
        captureApi.getSnapshot.mockResolvedValue({
            snapshot_id: 'snapshot-record',
            session_id: 'session-record',
            project_path: 'D:/projects/demo',
            workspace_id: 'workspace-demo',
            workspace_generation: 7,
            width: 960,
            height: 540,
            capture_context: {}
        })
        // 精确复现用户现场：项目接口目前只有 image 目录；前端仍必须补齐另外两个用途目录。
        visionApi.getTemplatesTree.mockResolvedValue({
            tree: [{ name: 'image', id: 'image', type: 'directory', children: [] }]
        })
        visionApi.getTemplatePreview.mockResolvedValue({ images: [] })
    })

    it('录入和视觉捕获保存时默认 image，但三个用途目录始终同时可选', async () => {
        const wrapper = mount(CaptureFileManagerView, {
            global: { plugins: [createPinia(), ElementPlus] }
        })
        expect(messageHandler).toBeTypeOf('function')

        messageHandler({
            data: {
                event: 'capture-save-context',
                version: 1,
                context: {
                    snapshot_id: 'snapshot-record',
                    kind: 'record',
                    category: 'image',
                    rects: [[10, 20, 30, 40]]
                }
            }
        })
        await flushPromises()

        expect(getWorkspaceIdentity()).toEqual({ workspaceId: 'workspace-demo', generation: 7 })

        const topLevelFolders = wrapper.findAll('.tree-wrapper > .el-tree > .el-tree-node')
        expect(topLevelFolders).toHaveLength(3)
        expect(topLevelFolders.map(node => node.text())).toEqual(expect.arrayContaining([
            expect.stringContaining('image'),
            expect.stringContaining('ocr'),
            expect.stringContaining('page')
        ]))
        expect(wrapper.text()).toContain('/templates/image')

        const pageFolder = topLevelFolders.find(node => node.text().includes('page'))
        await pageFolder.trigger('click')
        await flushPromises()
        expect(visionApi.getTemplatePreview).toHaveBeenLastCalledWith('D:/projects/demo', 'page')
        expect(wrapper.text()).toContain('/templates/page')
        wrapper.unmount()
        expect(getWorkspaceIdentity()).toBeNull()
    })
})
