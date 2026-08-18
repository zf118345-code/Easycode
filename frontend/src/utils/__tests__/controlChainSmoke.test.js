// frontend/src/utils/__tests__/controlChainSmoke.test.js
// ⚡ 控件链路端到端冒烟（A→B→C→G 串联）：
//   A schema 定义（与后端 core/params/base/control.py 对齐的 fixture）
//   → B buildNodeDefaultParams 按 schema 生成默认值
//   → C getNodeConfig 图标映射（NODE_ICON_MAP 有组件）
//   → G 捕获生成参数与 schema by 选项闭环一致
import { describe, it, expect } from 'vitest'
import { buildNodeDefaultParams } from '../nodeDefaults'
import { getNodeConfig } from '../../config/nodeRegistry'
import { NODE_ICON_MAP } from '../nodeIcons'
import { buildControlParamsFromInfo, buildControlNodeName } from '../captureNode'
import { CONTROL_SCHEMA } from '../../testFixtures/controlSchema'

describe('控件链路冒烟 A→B：schema → 默认值', () => {
    it('buildNodeDefaultParams 生成可执行参数（by 默认 UIA 名称、超时 3000）', () => {
        const defaults = buildNodeDefaultParams('control', { control: CONTROL_SCHEMA })
        expect(defaults.by).toBe('uia_name')
        expect(defaults.action).toBe('click')
        expect(defaults.timeout).toBe(3000)
        expect(defaults.target).toBe('')
        // 无 hidden 字段泄漏：键集合与 schema 完全一致
        expect(Object.keys(defaults).sort())
            .toEqual(Object.keys(CONTROL_SCHEMA.params).sort())
    })
})

describe('控件链路冒烟 B→C：默认值 → 图标/外观', () => {
    it('getNodeConfig(control) 的 icon 在 NODE_ICON_MAP 中有组件可渲染', () => {
        const config = getNodeConfig('control')
        expect(config.icon).toBe('ScanSearch')
        expect(config.modes).toContain('workflow')
        expect(NODE_ICON_MAP[config.icon]).toBeTruthy()
    })
})

describe('控件链路冒烟 G：捕获生成参数与 schema 闭环', () => {
    const byOptions = CONTROL_SCHEMA.params.by.options.map(o => o.value)

    it('捕获生成的 by 必然落在 schema by 选项内（前端与后端一致）', () => {
        const cases = [
            { name: '确定', control_type: 'button' },
            { control_type: 'edit' },
            { automation_id: 'e1' },
            { class_name: 'Button' }
        ]
        for (const info of cases) {
            const gen = buildControlParamsFromInfo(info)
            expect(byOptions).toContain(gen.by)
            expect(gen.target).toBeTruthy()
        }
    })

    it('完整链路：默认值 + 捕获参数 = 可直接用于执行的节点参数', () => {
        const defaults = buildNodeDefaultParams('control', { control: CONTROL_SCHEMA })
        const captured = buildControlParamsFromInfo({ name: '开始游戏', control_type: 'button' })
        const nodeParams = { ...defaults, ...captured }

        expect(nodeParams).toMatchObject({
            by: 'uia_name', target: '开始游戏', action: 'click', timeout: 3000
        })
        expect(buildControlNodeName({ name: '开始游戏' })).toBe('控件_开始游戏')
    })
})
