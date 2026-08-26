import { describe, it, expect, vi } from 'vitest'
import { handleError, ERROR_TYPES, withErrorHandling, safeCall } from '../errorHandler'

// Mock Element Plus
vi.mock('element-plus', () => ({
    ElMessage: vi.fn(),
    ElMessageBox: { confirm: vi.fn().mockRejectedValue('cancel') }
}))

describe('errorHandler', () => {
    it('handleError 对网络错误返回 NETWORK 类型', () => {
        const error = new Error('Network error')
        error.response = undefined
        const result = handleError(error, { silent: true })
        expect(result.type).toBe(ERROR_TYPES.NETWORK)
    })

    it('handleError 对 404 返回 NOT_FOUND', () => {
        const error = new Error('Not found')
        error.status = 404
        const result = handleError(error, { silent: true })
        expect(result.type).toBe(ERROR_TYPES.NOT_FOUND)
    })

    it('handleError 对 500 返回 SERVER', () => {
        const error = new Error('Server error')
        error.status = 500
        const result = handleError(error, { silent: true })
        expect(result.type).toBe(ERROR_TYPES.SERVER)
    })

    it('识别归一化后的客户端超时，而不是误报为断网', () => {
        const error = new Error('请求超时')
        error.name = 'ApiError'
        error.kind = 'timeout'
        expect(handleError(error, { silent: true }).type).toBe(ERROR_TYPES.TIMEOUT)
    })

    it.each([
        [409, ERROR_TYPES.CONFLICT],
        [408, ERROR_TYPES.TIMEOUT],
        [429, ERROR_TYPES.RATE_LIMIT],
        [503, ERROR_TYPES.SERVICE_UNAVAILABLE],
    ])('handleError 对状态码 %s 返回精确类型', (status, expected) => {
        const error = new Error('request failed')
        error.status = status
        expect(handleError(error, { silent: true }).type).toBe(expected)
    })

    it('withErrorHandling 成功时返回 success', async () => {
        const result = await withErrorHandling(async () => 42)
        expect(result.success).toBe(true)
        expect(result.data).toBe(42)
    })

    it('withErrorHandling 失败时返回 error', async () => {
        const result = await withErrorHandling(async () => {
            throw new Error('fail')
        }, { silent: true })
        expect(result.success).toBe(false)
    })

    it('safeCall 捕获异常', () => {
        const result = safeCall(() => {
            throw new Error('crash')
        }, { silent: true })
        expect(result).toBeNull()
    })
})
