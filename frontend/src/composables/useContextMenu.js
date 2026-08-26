// frontend/src/composables/useContextMenu.js
// 画布右键菜单与连线衍生菜单的共享状态。
import { reactive, ref } from 'vue'

/**
 * 画布右键菜单 composable
 * 命中检测由 CanvasView 完成，这里只保存菜单状态，避免把画布 DOM 规则
 * 重复维护在 composable 中。
 */
export function useContextMenu() {
    const customContextMenu = reactive({
        visible: false,
        x: 0,
        y: 0,
        targetType: 'canvas_public',  // 'node' | 'canvas_public'
        targetId: null,
        targetName: '',
        clientX: 0,
        clientY: 0
    })

    const spawnMenu = ref({
        visible: false,
        x: 0,
        y: 0,
        sourceNodeId: null,
        portType: 'success',
        clientX: 0,
        clientY: 0
    })

    return { customContextMenu, spawnMenu }
}
