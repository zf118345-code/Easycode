import { beforeEach, describe, expect, it, vi } from 'vitest'

const client = vi.hoisted(() => ({
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn()
}))

vi.mock('../client', () => ({ default: client }))

import { platformApi } from '../platformApi'

describe('platformApi scope contract', () => {
    beforeEach(() => {
        vi.clearAllMocks()
    })

    it('Player 状态、消息与租约都写入 Player 独立运行库', () => {
        platformApi.overview('player')
        platformApi.setState('progress', { page: 3 }, 'account-a', 'player')
        platformApi.publishMessage({ channel: 'team', payload: 1 }, 'player')
        platformApi.acquireLease({ resource_key: 'emulator-1', owner: 'instance-1' }, 'player')

        expect(client.get).toHaveBeenCalledWith('/api/platform/overview', { params: { scope: 'player' } })
        expect(client.put).toHaveBeenCalledWith('/api/platform/state/progress', { page: 3 }, { params: { scope: 'player', namespace: 'account-a' } })
        expect(client.post).toHaveBeenCalledWith('/api/platform/messages', expect.any(Object), { params: { scope: 'player' } })
        expect(client.post).toHaveBeenCalledWith('/api/platform/leases/acquire', expect.any(Object), { params: { scope: 'player' } })
    })

    it('Player 远程发送失败时使用 Player outbox，而远程租约保持实时调用', () => {
        const remote = { endpoint: 'http://coordinator:8000', token: 'secret', channel: 'team' }
        platformApi.publishRemote(remote, 'player')
        platformApi.acquireRemoteLease({ ...remote, resource_key: 'account-1', owner: 'instance-1' })

        expect(client.post).toHaveBeenCalledWith('/api/platform/remote/messages', remote, { params: { scope: 'player' } })
        expect(client.post).toHaveBeenCalledWith('/api/platform/remote/leases/acquire', expect.objectContaining({ resource_key: 'account-1' }))
    })
})
