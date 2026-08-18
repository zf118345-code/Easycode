// frontend/src/utils/nodeIcons.js
// 节点图标统一注册表（lucide）：icon 名（nodeRegistry.icon）→ 组件
// 画布卡片、节点列表、检查器统一从这里取，避免各组件维护重复映射
import {
    MousePointerClick, Timer, ScrollText, Image as ImageIcon, Type, GitBranch,
    Filter, Variable, Code, AppWindow, MapPin, Navigation, Square,
    Clock, SearchCheck, Binary, ListOrdered, FileCode, Target, ScanSearch
} from 'lucide-vue-next'

export const NODE_ICON_MAP = {
    MousePointerClick, Timer, ScrollText, Image: ImageIcon, Type, GitBranch,
    Filter, Variable, Code, AppWindow, MapPin, Navigation, Square,
    Clock, SearchCheck, Binary, ListOrdered, FileCode, Target, ScanSearch
}
