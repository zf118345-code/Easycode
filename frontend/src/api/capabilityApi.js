import client from './client'

export const capabilityApi = {
    list: (reload = false) => client.get('/api/capabilities', { params: { reload } }),
    createPackage: payload => client.post('/api/capabilities/packages', payload)
}
