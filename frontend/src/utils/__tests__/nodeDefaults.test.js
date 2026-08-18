// frontend/src/utils/__tests__/nodeDefaults.test.js
// 节点默认值生成：按后端 schema default 构建初始 params（控件节点全链路默认值）
import { describe, it, expect } from 'vitest'
import { buildNodeDefaultParams, NODE_DEFAULTS } from '../nodeDefaults'

// 与后端 core/params/base/control.py 对齐的 schema（默认值一致）
const CONTROL_DEFS = {
    control: {
        label: '控件操作',
        params: {
            action: { type: 'select', default: 'click' },
            by: { type: 'select', default: 'class_name' },
            target: { type: 'str', default: '' },
            window_title: { type: 'str', default: '' },
            index: { type: 'int', default: 0 },
            text_input: { type: 'str', default: '' },
            save_to_var: { type: 'str', default: '' },
            timeout: { type: 'int', default: 3000, suffix: 'ms' }
        }
    }
}

describe('buildNodeDefaultParams 节点默认值', () => {
    it('控件节点：操作=点击、查找=类名、超时 3000ms、序号 0、标识空', () => {
        const p = buildNodeDefaultParams('control', CONTROL_DEFS)
        expect(p.action).toBe('click')
        expect(p.by).toBe('class_name')
        expect(p.timeout).toBe(3000)
        expect(p.index).toBe(0)
        expect(p.target).toBe('')
        expect(p.window_title).toBe('')
        expect(p.text_input).toBe('')
        expect(p.save_to_var).toBe('')
    })

    it('未知类型/无定义：返回空对象', () => {
        expect(buildNodeDefaultParams('unknown_type', CONTROL_DEFS)).toEqual({})
        expect(buildNodeDefaultParams('control', undefined)).toEqual({})
    })

    it('隐藏字段跳过（page_state page_id 不进入默认参数）', () => {
        const p = buildNodeDefaultParams('page_state', {
            page_state: { params: { page_id: { type: 'str', hidden: true, default: 'auto' }, timeout: { type: 'int', default: 100 } } }
        })
        expect(p.page_id).toBeUndefined()
        expect(p.timeout).toBe(100)
    })

    it('数组默认值深拷贝，互不影响', () => {
        const defs = { click: { params: { position: { type: 'list_int2', default: [0, 0] } } } }
        const a = buildNodeDefaultParams('click', defs)
        const b = buildNodeDefaultParams('click', defs)
        a.position[0] = 99
        expect(b.position[0]).toBe(0)
    })

    it('通用节点默认延迟/循环与后端对齐', () => {
        expect(NODE_DEFAULTS.delayBefore).toBe(200)
        expect(NODE_DEFAULTS.loopCount).toBe(1)
    })
})
