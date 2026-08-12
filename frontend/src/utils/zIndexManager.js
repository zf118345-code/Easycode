// frontend/src/utils/zIndexManager.js
import { useZIndex } from 'element-plus'

/**
 * 工业级全局 Z-Index 动态分配器
 * 与 Element Plus 框架底层的 useZIndex 计数器打通
 * 确保 ScreenshotTool / 悬浮菜单 / 自定义 Dialog 永远压盖在当前最高层级之上
 */
export function getNextZIndex(offset = 15) {
    try {
        const { nextZIndex } = useZIndex()
        return nextZIndex() + offset
    } catch (e) {
        // 兜底防御
        window.__global_z_index = (window.__global_z_index || 3000) + offset
        return window.__global_z_index
    }
}