import { visionApi } from '@/api/visionApi'

const PREVIEW_CACHE_LIMIT = 128
const previewCache = new Map()

function touch(entry) {
    entry.lastUsed = Date.now()
}

function evictUnusedPreviews(force = false) {
    const candidates = [...previewCache.entries()]
        .filter(([, entry]) => entry.refs <= 0 && entry.url)
        .sort((a, b) => a[1].lastUsed - b[1].lastUsed)
    const removeCount = force ? candidates.length : Math.max(0, previewCache.size - PREVIEW_CACHE_LIMIT)
    for (const [key, entry] of candidates.slice(0, removeCount)) {
        URL.revokeObjectURL(entry.url)
        previewCache.delete(key)
    }
}

export function normalizeAssetReference(reference) {
    const value = String(reference || '').trim().replace(/\\/g, '/')
    if (!value || value.startsWith('http') || value.startsWith('data:') || value.startsWith('asset://')) {
        return value
    }
    return /\.(png|jpg|jpeg)$/i.test(value) ? value : `${value}.png`
}

export async function loadAssetPreview(projectPath, reference, assetRevision = 0) {
    const normalized = normalizeAssetReference(reference)
    if (!normalized) throw new Error('未指定图片资源')
    if (normalized.startsWith('http') || normalized.startsWith('data:')) {
        return { url: normalized, revoke: false }
    }
    if (!projectPath) throw new Error('当前没有打开项目')

    // A resource mutation explicitly clears this cache. Graph revisions are not
    // part of the key: moving a node or editing an edge must never reload every
    // unchanged thumbnail on the canvas.
    const cacheKey = `${projectPath}\n${normalized}\n${assetRevision}`
    let entry = previewCache.get(cacheKey)
    if (!entry) {
        entry = { refs: 0, url: '', promise: null, lastUsed: Date.now() }
        entry.promise = visionApi.getImageThumb(projectPath, normalized)
            .then(blob => {
                if (!(blob instanceof Blob)) throw new Error('缩略图接口没有返回图片数据')
                entry.url = URL.createObjectURL(blob)
                touch(entry)
                evictUnusedPreviews()
                return entry.url
            })
            .catch(error => {
                previewCache.delete(cacheKey)
                throw error
            })
        previewCache.set(cacheKey, entry)
    }
    entry.refs += 1
    touch(entry)
    const url = entry.url || await entry.promise
    return { url, revoke: false, cacheKey }
}

export function releaseAssetPreview(preview) {
    if (preview?.cacheKey) {
        const entry = previewCache.get(preview.cacheKey)
        if (entry) {
            entry.refs = Math.max(0, entry.refs - 1)
            touch(entry)
            evictUnusedPreviews()
        }
        return
    }
    if (preview?.revoke && preview.url) URL.revokeObjectURL(preview.url)
}

export function clearAssetPreviewCache() {
    evictUnusedPreviews(true)
}
