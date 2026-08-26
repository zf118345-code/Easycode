import { describe, expect, it, vi } from 'vitest'
import { ElMessage } from 'element-plus'
import { isUserCancellation, notifyActionError } from '@/utils/userActionErrors'

vi.mock('element-plus', () => ({ ElMessage: { error: vi.fn() } }))

describe('userActionErrors', () => {
    it('只静默用户主动取消，不吞掉真实错误', () => {
        expect(isUserCancellation('cancel')).toBe(true)
        expect(isUserCancellation('close')).toBe(true)
        expect(isUserCancellation(new Error('保存失败'))).toBe(false)
    })

    it('真实错误使用具体消息提示', () => {
        expect(notifyActionError(new Error('磁盘空间不足'), '保存失败')).toBe(true)
        expect(ElMessage.error).toHaveBeenCalledWith('磁盘空间不足')
    })
})
