import { describe, it, expect } from 'vitest'
import {
    NODE_REGISTRY,
    DEFAULT_NODE_CONFIG,
    getNodeConfig,
    getNodeTypesForMode,
    getNodeContentSpec,
    estimateNodeContentHeight
} from '../../config/nodeRegistry'

describe('nodeRegistry 统一注册表', () => {
    it('getNodeTypesForMode 按 modes 过滤可用类型', () => {
        const workflowTypes = getNodeTypesForMode('workflow')
        expect(workflowTypes.click).toBeTruthy()
        expect(workflowTypes.branch).toBeTruthy()
        expect(workflowTypes.page_state).toBeUndefined()

        const topologyTypes = getNodeTypesForMode('topology')
        expect(topologyTypes.page_state).toBeTruthy()
        // smart_jump 是主流程专属节点，拓扑画布不再出现
        expect(topologyTypes.smart_jump).toBeUndefined()
        expect(topologyTypes.click).toBeTruthy()
        expect(topologyTypes.branch).toBeUndefined()
    })

    it('控件节点：workflow 画布可用、拓扑不可用，外观/内容规则完整', () => {
        expect(getNodeTypesForMode('workflow').control).toBe('控件操作')
        expect(getNodeTypesForMode('topology').control).toBeUndefined()
        expect(getNodeConfig('control').icon).toBe('ScanSearch')
        expect(getNodeConfig('control').color).toBe('#00bcd4')
        expect(getNodeContentSpec('control')).toBeNull()
    })

    it('getNodeConfig 返回外观配置，未知类型回退默认', () => {
        expect(getNodeConfig('click').icon).toBe('MousePointerClick')
        expect(getNodeConfig('click').label).toBe('鼠标点击')
        expect(getNodeConfig('unknown_type')).toBe(DEFAULT_NODE_CONFIG)
    })

    it('后端 /api/params 配置优先：label/modes 以后端为准，icon/color/content 保留前端', () => {
        const backendDefs = {
            click: { label: '后端点击名', modes: ['topology'], params: {} },
            brand_new_type: { label: '后端新增类型', modes: ['workflow'], params: {} }
        }
        // label 优先后端
        expect(getNodeConfig('click', backendDefs).label).toBe('后端点击名')
        // icon/color 仍来自前端表
        expect(getNodeConfig('click', backendDefs).icon).toBe('MousePointerClick')
        expect(getNodeConfig('click', backendDefs).color).toBe('#409eff')
        // modes 以后端为准（click 只允许 topology）
        const topologyTypes = getNodeTypesForMode('topology', backendDefs)
        expect(topologyTypes.click).toBe('后端点击名')
        expect(getNodeTypesForMode('workflow', backendDefs).click).toBeUndefined()
        // 后端新增类型自动进入白名单（前端零修改）
        expect(getNodeTypesForMode('workflow', backendDefs).brand_new_type).toBe('后端新增类型')
    })

    it('getNodeContentSpec：无内容类型返回 null，有内容类型返回规则', () => {
        expect(getNodeContentSpec('click')).toBeNull()
        expect(getNodeContentSpec('wait')).toBeNull()
        expect(getNodeContentSpec('log')).toBeNull()
        expect(getNodeContentSpec('variable_op')).toBeNull()
        expect(getNodeContentSpec('script_call')).toBeNull()
        expect(getNodeContentSpec('smart_jump')).toBeNull()
        expect(getNodeContentSpec('logic_check')).toBeNull()
        expect(getNodeContentSpec('image_recognition').kind).toBe('image')
        expect(getNodeContentSpec('ocr_recognition').kind).toBe('ocr')
        expect(getNodeContentSpec('branch').kind).toBe('branch-candidates')
        expect(getNodeContentSpec('page_state').kind).toBe('page-info')
    })

    it('estimateNodeContentHeight：无内容 = 0', () => {
        expect(estimateNodeContentHeight({ node_type: 'click', params: { position: [1, 2] } })).toBe(0)
        expect(estimateNodeContentHeight({ node_type: 'wait', params: { seconds: 1 } })).toBe(0)
    })

    it('estimateNodeContentHeight：image / ocr 取最小高度', () => {
        expect(estimateNodeContentHeight({ node_type: 'image_recognition', params: {} })).toBe(80)
        expect(estimateNodeContentHeight({ node_type: 'ocr_recognition', params: {} })).toBe(60)
    })

    it('estimateNodeContentHeight：branch 每候选一行 + 空态占位一行', () => {
        const spec = NODE_REGISTRY.branch.content
        const twoCand = { node_type: 'branch', params: { candidates: [{}, {}] } }
        expect(estimateNodeContentHeight(twoCand)).toBe(2 * spec.rowHeight + spec.rowGap + spec.rowPadding)

        const empty = { node_type: 'branch', params: { candidates: [] } }
        expect(estimateNodeContentHeight(empty)).toBe(spec.rowHeight + spec.rowPadding)
    })

    it('estimateNodeContentHeight：page-info 只按出口行计高（dynamicCount 由画布边推导）', () => {
        const spec = NODE_REGISTRY.page_state.content
        // 2 个出口行（含占位）：12 + 2*24 + 1*4 = 64
        const withExits = { node_type: 'page_state', params: {} }
        expect(estimateNodeContentHeight(withExits, 2)).toBe(
            spec.rowPadding + 2 * spec.exitRowHeight + spec.exitRowGap)

        // 无出口 → 0（特征详情在属性面板，不占卡片高度）
        const bare = { node_type: 'page_state', params: { features: [{}] } }
        expect(estimateNodeContentHeight(bare)).toBe(0)
    })

    it('注册表为单一事实源：所有类型都定义了 modes 且 content 规则完整', () => {
        for (const [type, cfg] of Object.entries(NODE_REGISTRY)) {
            expect(Array.isArray(cfg.modes)).toBe(true)
            expect(cfg.modes.length).toBeGreaterThan(0)
            expect(cfg.label).toBeTruthy()
            expect(cfg.icon).toBeTruthy()
            if (cfg.content) {
                expect(['image', 'ocr', 'branch-candidates', 'page-info']).toContain(cfg.content.kind)
            }
        }
    })

    it('B2：每个节点的 icon 名都映射到 lucide 组件（节点列表/画布统一取图，新增类型不漏映射）', async () => {
        const { NODE_ICON_MAP } = await import('@/utils/nodeIcons')
        for (const [type, cfg] of Object.entries(NODE_REGISTRY)) {
            expect(NODE_ICON_MAP[cfg.icon], `icon 未映射: ${type} -> ${cfg.icon}`).toBeTruthy()
        }
    })
})
