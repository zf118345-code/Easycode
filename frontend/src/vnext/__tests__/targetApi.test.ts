import { afterEach, describe, expect, it, vi } from 'vitest'

import { VNextApiError, vnextApi } from '../api'
import type { TargetDefinition } from '../types'

const workspace = {
    workspace_id: 'workspace-targets',
    generation: 9,
    project_id: 'project-targets',
    project_name: '目标测试',
    project_path: 'D:/Projects/Targets',
    read_only: false,
}

function response(payload: unknown, status = 200): Response {
    return {
        ok: status >= 200 && status < 300,
        status,
        json: vi.fn().mockResolvedValue(payload),
    } as unknown as Response
}

describe('format-6 target API contract', () => {
    afterEach(() => { vi.unstubAllGlobals() })

    it('sends the independent expected revision and strict discriminated targets', async () => {
        const targets: TargetDefinition[] = [
            {
                target_id: 'target-window',
                name: '游戏窗口',
                type: 'windows',
                window_title: '传奇',
                window_match: 'contains',
                work_area: { mode: 'client' },
                allow_physical_fallback: true,
            },
            {
                target_id: 'target-adb',
                name: '雷电模拟器',
                type: 'android_adb',
                device_serial: 'emulator-5554',
            },
            {
                target_id: 'target-local',
                name: '当前手机',
                type: 'android_local',
            },
        ]
        const fetchMock = vi.fn().mockResolvedValue(response({
            schema_version: 1,
            targets,
            default_target_id: 'target-window',
            revision: 'sha256:next',
        }))
        vi.stubGlobal('fetch', fetchMock)

        await vnextApi.saveTargets(workspace, 'sha256:current', targets, 'target-window')

        const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit]
        expect(url).toBe('/api/vnext/targets')
        expect(init.headers).toMatchObject({
            'X-Workspace-Id': 'workspace-targets',
            'X-Workspace-Generation': '9',
        })
        expect(JSON.parse(String(init.body))).toEqual({
            expected_revision: 'sha256:current',
            targets,
            default_target_id: 'target-window',
        })
        expect(JSON.parse(String(init.body)).targets[1]).not.toHaveProperty('work_area')
        expect(JSON.parse(String(init.body)).targets[2]).not.toHaveProperty('device_serial')
    })

    it('preserves server diagnostics for explicit 409 conflict recovery', async () => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({
            detail: {
                code: 'target_revision_conflict',
                message: '目标配置已经变化',
                diagnostics: [{ expected_revision: 'sha256:old', actual_revision: 'sha256:new' }],
                recovery: { action: 'reload_workspace', retryable: false },
            },
        }, 409)))

        const error = await vnextApi.saveTargets(workspace, 'sha256:old', [], null).catch((reason: unknown) => reason)
        expect(error).toBeInstanceOf(VNextApiError)
        expect(error).toMatchObject({
            status: 409,
            code: 'target_revision_conflict',
            recoveryAction: 'reload_workspace',
            diagnostics: [{ expected_revision: 'sha256:old', actual_revision: 'sha256:new' }],
        })
    })
})
