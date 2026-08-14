// useCanvasSharedStyle.js
// 将 canvasShared.js 中的 SHARED_EDGE_CSS / SHARED_NODE_CSS 注入到 <head> 一次，
// 供 WorkflowCanvas / TopologyCanvas 及其子组件（CanvasNodeCard / CanvasEdgeLayer）共享。
//
// 设计要点：
// - 幂等：多次调用只注入一次（通过 data-canvas-shared 标记判断）。
// - 全局（非 scoped）：子组件内部的 .edge-path / .node-header / .node-port 等元素
//   无法被父组件 scoped 样式覆盖，必须通过全局注入才能统一外观。
// - 各画布仍可在自身 <style scoped> 中覆盖（scoped 优先级更高）。

import { SHARED_EDGE_CSS, SHARED_NODE_CSS } from '@/utils/canvasShared'

const INJECT_FLAG = 'data-canvas-shared'
const INJECT_ID = 'canvas-shared-style'

let injected = false

export function useCanvasSharedStyle() {
    if (injected) return
    if (typeof document === 'undefined') return

    // 防止重复注入
    if (document.getElementById(INJECT_ID)) {
        injected = true
        return
    }

    const styleEl = document.createElement('style')
    styleEl.setAttribute('id', INJECT_ID)
    styleEl.setAttribute(INJECT_FLAG, 'true')
    styleEl.textContent = `${SHARED_EDGE_CSS}\n${SHARED_NODE_CSS}`
    document.head.appendChild(styleEl)
    injected = true
}
