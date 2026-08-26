import client from './client'

export const workspaceApi = {
    saveContext: (projectPath, context) => client.post('/api/context', {
        project_path: projectPath,
        context
    }),

    getContext: projectPath => client.get('/api/context', {
        params: { project_path: projectPath }
    }),

    getFullScreenshot: projectPath => client.get('/api/screenshot/full', {
        params: { project_path: projectPath }
    }),

    cropScreenshot: (projectPath, templateName, cropRect) => client.post('/api/screenshot/crop', {
        project_path: projectPath,
        template_name: templateName,
        crop_rect: cropRect
    }),

    getWindows: () => client.get('/api/windows'),

    getAdbDevices: () => client.get('/api/adb/devices'),

    resolveAdbDevice: ({ windowTitle, windowHwnd, processId }) => client.post('/api/adb/resolve', {
        window_title: windowTitle,
        window_hwnd: windowHwnd,
        process_id: processId
    })
}
