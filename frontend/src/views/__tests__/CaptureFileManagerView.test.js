import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, shallowMount } from '@vue/test-utils'
import CaptureFileManagerView from '@/views/CaptureFileManagerView.vue'
import FileBrowser from '@/components/FileBrowser.vue'
import { captureApi } from '@/api/captureApi'

vi.mock('@/api/captureApi', () => ({
    captureApi: {
        getSnapshot: vi.fn(),
        saveAssets: vi.fn(),
        requestAction: vi.fn(),
        undoAssets: vi.fn()
    }
}))

describe('CaptureFileManagerView 常驻宿主协议', () => {
    let messageHandler
    let postMessage

    beforeEach(() => {
        vi.clearAllMocks()
        messageHandler = null
        postMessage = vi.fn()
        Object.defineProperty(window, 'chrome', {
            configurable: true,
            writable: true,
            value: {
                webview: {
                    postMessage,
                    addEventListener: vi.fn((type, handler) => {
                        if (type === 'message') messageHandler = handler
                    }),
                    removeEventListener: vi.fn()
                }
            }
        })
        window.history.replaceState({}, '', '/')
        captureApi.getSnapshot.mockImplementation(snapshotId => Promise.resolve({
            snapshot_id: snapshotId,
            session_id: `session-${snapshotId}`,
            project_path: `D:/projects/${snapshotId}`,
            workspace_id: `workspace-${snapshotId}`,
            workspace_generation: 3,
            width: 800,
            height: 600,
            capture_context: {}
        }))
    })

    it('启动只报告 ready，并可反复接收上下文而不重建页面宿主', async () => {
        const wrapper = shallowMount(CaptureFileManagerView)
        expect(postMessage).toHaveBeenCalledWith({ event: 'capture-file-manager-ready', version: 1 })
        expect(messageHandler).toBeTypeOf('function')

        messageHandler({
            data: {
                event: 'capture-save-context',
                version: 1,
                context: { snapshot_id: 'snap-a', kind: 'image', rects: [[1, 2, 3, 4]] }
            }
        })
        await flushPromises()
        expect(captureApi.getSnapshot).toHaveBeenLastCalledWith('snap-a', false)
        expect(wrapper.findComponent(FileBrowser).props('projectPath')).toBe('D:/projects/snap-a')

        messageHandler({
            data: {
                event: 'capture-save-context',
                version: 1,
                context: { snapshot_id: 'snap-b', kind: 'ocr', rects: [[5, 6, 7, 8]] }
            }
        })
        await flushPromises()
        expect(captureApi.getSnapshot).toHaveBeenLastCalledWith('snap-b', false)
        expect(wrapper.findComponent(FileBrowser).props('projectPath')).toBe('D:/projects/snap-b')
        expect(wrapper.findComponent(FileBrowser).props('initialPath')).toBe('ocr')
        wrapper.unmount()
    })

    it('以用户最终选择的根目录作为资源分类，而不是固定使用初始目录', async () => {
        captureApi.saveAssets.mockResolvedValue({
            files: ['templates/ocr/ocr_test.png'],
            rects: [[1, 2, 3, 4]],
            template_keys: ['ocr/ocr_test'],
            asset_refs: ['asset://ocr_test'],
            assets: [{ asset_id: 'ocr_test', display_name: 'ocr_test' }],
            transaction_id: 'asset_tx_test'
        })
        captureApi.requestAction.mockResolvedValue({ ok: true })
        const wrapper = shallowMount(CaptureFileManagerView)
        messageHandler({
            data: {
                event: 'capture-save-context',
                version: 1,
                context: { snapshot_id: 'snap-record', kind: 'record', rects: [[1, 2, 3, 4]] }
            }
        })
        await flushPromises()

        wrapper.findComponent(FileBrowser).vm.$emit('save', { relativePath: 'ocr', fileName: '' })
        await flushPromises()

        expect(captureApi.saveAssets).toHaveBeenCalledWith(expect.objectContaining({
            category: 'ocr',
            relative_dir: 'ocr'
        }))
        expect(captureApi.requestAction).toHaveBeenCalledWith(expect.objectContaining({
            captured_assets: [{ asset_id: 'ocr_test', display_name: 'ocr_test' }]
        }))
        wrapper.unmount()
    })

    it('IDE 拒绝捕获结果时回滚资源事务并保持保存窗口打开', async () => {
        captureApi.saveAssets.mockResolvedValue({
            ok: true,
            files: ['assets/page/dialog/asset_1.png'],
            rects: [[1, 2, 3, 4]],
            template_keys: [],
            asset_refs: ['asset://asset_1'],
            transaction_id: 'asset_tx_rejected'
        })
        captureApi.requestAction.mockResolvedValue({ ok: false, message: '字段 revision 已变化，请重新捕获' })
        captureApi.undoAssets.mockResolvedValue({ ok: true })
        const wrapper = shallowMount(CaptureFileManagerView)
        messageHandler({
            data: {
                event: 'capture-save-context',
                version: 1,
                context: {
                    snapshot_id: 'snap-rejected', kind: 'field_confirm', destination: 'resource',
                    field_request_id: 'resource_capture_1', rects: [[1, 2, 3, 4]]
                }
            }
        })
        await flushPromises()

        expect(wrapper.findComponent(FileBrowser).props('saveButtonText')).toBe('录入资源')
        wrapper.findComponent(FileBrowser).vm.$emit('save', { relativePath: 'page/dialog', fileName: 'dialog' })
        await flushPromises()

        expect(captureApi.undoAssets).toHaveBeenCalledWith('asset_tx_rejected')
        expect(postMessage).not.toHaveBeenCalledWith(expect.objectContaining({ event: 'capture-save-complete' }))
        expect(wrapper.findComponent(FileBrowser).exists()).toBe(true)
        wrapper.unmount()
    })
})
