import { describe, it, expect, vi } from 'vitest'
import { handleError, ERROR_TYPES, withErrorHandling, confirmAction, safeCall } from '../errorHandler'

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
