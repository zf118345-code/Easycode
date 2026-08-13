// frontend/src/api/workspaceApi.js
// 工作区上下文 API：对齐后端 /api/context 和 /api/screenshot 路由
// 修复：该文件此前缺失，导致 stores/index.js 导入失败

import client from './client'

export const workspaceApi = {
    // 保存工作区上下文
    saveContext: (projectPath, context) => client.post('/api/context', {
        project_path: projectPath,
        context
    }),

    // 获取工作区上下文
    getContext: (projectPath) => client.get('/api/context', {
        params: { project_path: projectPath }
    }),

    // 获取全屏截图
    getFullScreenshot: (projectPath) => client.get('/api/screenshot/full', {
        params: { project_path: projectPath }
    }),

    // 截图裁剪保存为模板
    cropScreenshot: (projectPath, templateName, cropRect) => client.post('/api/screenshot/crop', {
        project_path: projectPath,
        template_name: templateName,
        crop_rect: cropRect
    }),

    // 自定义截图
    takeScreenshot: (requestData) => client.post('/api/screenshot', requestData),

    // 获取窗口列表
    getWindows: () => client.get('/api/windows')
}