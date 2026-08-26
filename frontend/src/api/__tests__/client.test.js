import { describe, expect, it } from 'vitest'

import { normalizeApiError } from '@/api/client'

describe('API 错误归一化', () => {
    it('保留后端错误码、状态和结构化详情', () => {
        const error = normalizeApiError({
            response: {
                status: 409,
                data: {
                    code: 301,
                    message: '资源正在被其他实例使用',
                    data: { owner: 'instance-2' },
                },
                headers: { 'retry-after': '3' },
            },
        })

        expect(error).toMatchObject({
            message: '资源正在被其他实例使用',
            status: 409,
            code: 301,
            details: { owner: 'instance-2' },
            retryAfter: '3',
            retryable: false,
        })
    })

    it('区分超时和无法连接，并标记为可重试', () => {
        const timeout = normalizeApiError({ code: 'ECONNABORTED', message: 'timeout of 30000ms exceeded' })
        const offline = normalizeApiError({ request: {}, message: 'Network Error' })

        expect(timeout.message).toContain('请求超时')
        expect(timeout.kind).toBe('timeout')
        expect(timeout.retryable).toBe(true)
        expect(offline.message).toContain('无法连接')
        expect(offline.kind).toBe('network')
        expect(offline.retryable).toBe(true)
    })

    it('从 FastAPI 结构化 detail 提取可读消息而不是显示 object', () => {
        const error = normalizeApiError({
            response: {
                status: 422,
                data: {
                    detail: {
                        message: '发布前检查未通过',
                        preflight: { counts: { error: 2 } },
                    },
                },
                headers: {},
            },
        })

        expect(error.message).toBe('发布前检查未通过')
        expect(error.details.preflight.counts.error).toBe(2)
    })
})
