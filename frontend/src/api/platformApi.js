import client from './client'

const scopeParams = scope => ({ scope })

export const platformApi = {
    overview: (scope = 'ide') => client.get('/api/platform/overview', { params: scopeParams(scope) }),
    listStates: (scope = 'ide', namespace = undefined) => client.get('/api/platform/state-values', { params: { ...scopeParams(scope), namespace } }),
    setState: (key, value, namespace = 'default', scope = 'ide') => client.put(`/api/platform/state/${encodeURIComponent(key)}`, value, { params: { ...scopeParams(scope), namespace } }),
    deleteState: (key, namespace = 'default', scope = 'ide') => client.delete(`/api/platform/state/${encodeURIComponent(key)}`, { params: { ...scopeParams(scope), namespace } }),
    listSchedules: (scope = 'ide') => client.get('/api/platform/schedules', { params: scopeParams(scope) }),
    saveSchedule: (payload, scope = 'ide') => client.post('/api/platform/schedules', payload, { params: scopeParams(scope) }),
    deleteSchedule: (id, scope = 'ide') => client.delete(`/api/platform/schedules/${encodeURIComponent(id)}`, { params: scopeParams(scope) }),
    outboxStatus: (scope = 'ide') => client.get('/api/platform/outbox', { params: scopeParams(scope) }),
    listMessages: (scope = 'ide', channel = undefined) => client.get('/api/platform/messages', { params: { ...scopeParams(scope), channel } }),
    publishMessage: (payload, scope = 'ide') => client.post('/api/platform/messages', payload, { params: scopeParams(scope) }),
    claimMessages: (payload, scope = 'ide') => client.post('/api/platform/messages/claim', payload, { params: scopeParams(scope) }),
    ackMessage: (id, consumer, scope = 'ide') => client.post(`/api/platform/messages/${encodeURIComponent(id)}/ack`, { consumer }, { params: scopeParams(scope) }),
    listLeases: (scope = 'ide') => client.get('/api/platform/leases', { params: scopeParams(scope) }),
    acquireLease: (payload, scope = 'ide') => client.post('/api/platform/leases/acquire', payload, { params: scopeParams(scope) }),
    renewLease: (payload, scope = 'ide') => client.post('/api/platform/leases/renew', payload, { params: scopeParams(scope) }),
    releaseLease: (payload, scope = 'ide') => client.post('/api/platform/leases/release', payload, { params: scopeParams(scope) }),
    publishRemote: (payload, scope = 'ide') => client.post('/api/platform/remote/messages', payload, { params: scopeParams(scope) }),
    claimRemote: payload => client.post('/api/platform/remote/messages/claim', payload),
    ackRemote: (id, payload) => client.post(`/api/platform/remote/messages/${encodeURIComponent(id)}/ack`, payload),
    acquireRemoteLease: payload => client.post('/api/platform/remote/leases/acquire', payload),
    renewRemoteLease: payload => client.post('/api/platform/remote/leases/renew', payload),
    releaseRemoteLease: payload => client.post('/api/platform/remote/leases/release', payload)
}
