// frontend/src/api/workspaceApi.js
import client from './client'

export const workspaceApi = {
    getWindows: () => client.get('/api/windows'),
    getContext: (projectPath) => client.get('/api/context', { params: { project_path: projectPath } }),
    saveContext: (projectPath, context) => client.post('/api/context', { project_path: projectPath, context }),
    getFullScreenshot: (projectPath) => client.get('/api/screenshot/full', { params: { project_path: projectPath } }),
    cropScreenshot: (projectPath, templateName, cropRect) => client.post('/api/screenshot/crop', { project_path: projectPath, template_name: templateName, crop_rect: cropRect })
}