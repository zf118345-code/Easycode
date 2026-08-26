import client from './client'

export const projectWorkspaceApi = {
    active: () => client.get('/api/workspaces/active'),
    recent: () => client.get('/api/workspaces/recent'),
    changes: () => client.get('/api/workspaces/changes'),
    acknowledge: () => client.post('/api/workspaces/acknowledge'),
    inspect: (path) => client.post('/api/workspaces/inspect', { path }),
    open: (payload) => client.post('/api/workspaces/open', payload),
    repair: (path) => client.post('/api/workspaces/repair', { path, confirmed: true }),
    close: () => client.post('/api/workspaces/close'),
    removeRecent: (path) => client.delete('/api/workspaces/recent', { data: { path } }),
    chooseFolder: (title = '选择 EasyCode 项目文件夹') => client.post('/api/workspaces/choose-folder', { title }),
    chooseFile: (title = '选择文件', extensions = []) => client.post('/api/workspaces/choose-file', { title, extensions })
}
