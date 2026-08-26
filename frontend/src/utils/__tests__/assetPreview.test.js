import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { clearAssetPreviewCache, loadAssetPreview, normalizeAssetReference, releaseAssetPreview } from '@/utils/assetPreview'
import { visionApi } from '@/api/visionApi'

vi.mock('@/api/visionApi', () => ({
    visionApi: { getImageThumb: vi.fn() }
}))

describe('assetPreview', () => {
    beforeEach(() => {
        vi.clearAllMocks()
        vi.stubGlobal('URL', {
            createObjectURL: vi.fn(() => 'blob:preview'),
            revokeObjectURL: vi.fn()
        })
    })

    afterEach(() => {
        clearAssetPreviewCache()
        vi.unstubAllGlobals()
    })

    it('保持 asset:// 稳定引用不追加扩展名', () => {
        expect(normalizeAssetReference('asset://asset_123')).toBe('asset://asset_123')
    })

    it('为旧式无扩展名路径补 png，并统一路径分隔符', () => {
        expect(normalizeAssetReference('image\\button')).toBe('image/button.png')
        expect(normalizeAssetReference('image/button.jpg')).toBe('image/button.jpg')
    })

    it('同一资源的并发和重复预览只请求一次，只有显式资源失效才刷新', async () => {
        visionApi.getImageThumb.mockResolvedValue(new Blob(['png'], { type: 'image/png' }))
        const [first, second] = await Promise.all([
            loadAssetPreview('D:/project', 'image/button.png'),
            loadAssetPreview('D:/project', 'image/button.png')
        ])
        expect(visionApi.getImageThumb).toHaveBeenCalledTimes(1)
        expect(first.url).toBe(second.url)
        releaseAssetPreview(first)
        releaseAssetPreview(second)

        const refreshed = await loadAssetPreview('D:/project', 'image/button.png', 1)
        expect(visionApi.getImageThumb).toHaveBeenCalledTimes(2)
        releaseAssetPreview(refreshed)
    })
})
