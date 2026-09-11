import { afterEach, describe, expect, it, vi } from 'vitest'

import { vnextApi } from '../api'

const workspace = {
    workspace_id: 'workspace-idempotency',
    generation: 7,
    project_id: 'project-idempotency',
    project_name: '幂等测试',
    project_path: 'D:/Projects/Idempotency',
    read_only: false,
}

function response(payload: unknown) {
    return { ok: true, status: 200, json: vi.fn().mockResolvedValue(payload) } as unknown as Response
}

describe('vNext API idempotency adapter', () => {
    afterEach(() => { vi.unstubAllGlobals() })

    it('合并并发重复保存，成功后下一次用户操作使用新键', async () => {
        let complete: (value: Response) => void = () => undefined
        const form = { schema_version: 3 as const, title: '脚本运行器', pages: [] }
        const fetchMock = vi.fn()
            .mockReturnValueOnce(new Promise<Response>(resolve => { complete = resolve }))
            .mockResolvedValueOnce(response(form))
        vi.stubGlobal('fetch', fetchMock)

        const first = vnextApi.savePlayerForm(workspace, form)
        const duplicate = vnextApi.savePlayerForm(workspace, form)
        expect(fetchMock).toHaveBeenCalledTimes(1)
        const firstKey = (fetchMock.mock.calls[0][1].headers as Record<string, string>)['Idempotency-Key']

        complete(response(form))
        await Promise.all([first, duplicate])
        await vnextApi.savePlayerForm(workspace, form)

        expect(fetchMock).toHaveBeenCalledTimes(2)
        const secondKey = (fetchMock.mock.calls[1][1].headers as Record<string, string>)['Idempotency-Key']
        expect(firstKey).toMatch(/^ide-player-form:/)
        expect(secondKey).not.toBe(firstKey)
    })

    it('连接结果不确定时使用同一键重试，避免后台执行两次', async () => {
        const fetchMock = vi.fn()
            .mockRejectedValueOnce(new TypeError('network disconnected'))
            .mockResolvedValueOnce(response({
                execution_id: 'run-1', status: 'queued', started_at: '', finished_at: '', error: '',
                events: [], current_instruction_id: '', current_source: {}, variables: {}, breakpoints: [],
                diagnostic_available: false, failure_frame_available: false,
            }))
        vi.stubGlobal('fetch', fetchMock)
        const payload = { target_id: 'target-1', player_values: { seat: 'A1' } }

        await expect(vnextApi.playerRuntimeRun(payload)).rejects.toMatchObject({ status: 503 })
        await vnextApi.playerRuntimeRun(payload)

        const firstKey = (fetchMock.mock.calls[0][1].headers as Record<string, string>)['Idempotency-Key']
        const retryKey = (fetchMock.mock.calls[1][1].headers as Record<string, string>)['Idempotency-Key']
        expect(retryKey).toBe(firstKey)
    })
})
