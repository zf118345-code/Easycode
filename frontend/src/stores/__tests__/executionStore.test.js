// frontend/src/stores/__tests__/executionStore.test.js
// 调试状态轮询行为：
// 1. 会话 404（执行已结束）→ 静默收敛并停止轮询，不再产生 warn 噪音
// 2. 变量快照：非暂停时保留上一节点值（prev），避免单步瞬间闪为 —；暂停时替换
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useExecutionStore } from '@/stores/executionStore'

vi.mock('@/api/executionApi', () => ({
    executionApi: {
        getDebugState: vi.fn()
    }
}))

import { executionApi } from '@/api/executionApi'

describe('executionStore.pollDebugState', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
    })

    it('会话 404 时静默收敛（不抛错、不打印 warn）', async () => {
        const store = useExecutionStore()
        store.currentExecutionId = 'exec_404'
        const err = new Error('调试会话不存在')
        err.status = 404
        executionApi.getDebugState.mockRejectedValue(err)

        // ⚡ #5 调试状态已随 SSE 推送：startDebugPolling 只做一次性同步，不再创建轮询定时器
        store.startDebugPolling(10000)
        expect(store._pollTimer).toBeNull()

        const result = await store.pollDebugState()

        expect(result).toBeNull()
        expect(store._pollTimer).toBeNull()
        expect(store.executionState).not.toBe('running')  // 不误改状态
    })

    it('非暂停轮询：current 更新为实时值，prev 保留旧值（防闪烁）', async () => {
        const store = useExecutionStore()
        store.currentExecutionId = 'exec_1'
        store.executionPrevVariables = { coin: 5 }  // 上一次暂停留下的快照

        executionApi.getDebugState.mockResolvedValue({
            is_paused: false,
            executor_variables: { coin: 9 }
        })

        await store.pollDebugState()

        expect(store.executionCurrentVariables).toEqual({ coin: 9 })
        expect(store.executionPrevVariables).toEqual({ coin: 5 })  // 保留，不清空
    })

    it('暂停轮询：prev 替换为后端 prev_variables', async () => {
        const store = useExecutionStore()
        store.currentExecutionId = 'exec_2'
        store.executionPrevVariables = { coin: 5 }

        executionApi.getDebugState.mockResolvedValue({
            is_paused: true,
            executor_variables: { coin: 9 },
            prev_variables: { coin: 5 }
        })

        await store.pollDebugState()

        expect(store.executionState).toBe('paused')
        expect(store.executionCurrentVariables).toEqual({ coin: 9 })
        expect(store.executionPrevVariables).toEqual({ coin: 5 })
    })
})
