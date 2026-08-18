// frontend/src/api/uiControlApi.js
// 控件捕获工具接口：捕获模式 + 快捷键配置（识别为悬停自动、高亮为后端驱动，前端零轮询）
import client from './client'

export const uiControlApi = {
    // 捕获模式：状态查询 / 进入退出（action: start | stop）
    mode: () => client.get('/api/ui-control/mode'),
    modeControl: (action) => client.post('/api/ui-control/mode', { action }),
    // 全局快捷键配置（编辑菜单 → 快捷键设置）
    getHotkeys: () => client.get('/api/settings/hotkeys'),
    putHotkeys: (hotkeys) => client.put('/api/settings/hotkeys', { hotkeys })
}
