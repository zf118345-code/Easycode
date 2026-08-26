import { describe, expect, it } from 'vitest'
import { buildPlayerConfig, normalizePlayerSchema, validatePlayerConfig } from '@/utils/playerSchema'

describe('Player Schema v3', () => {
    it('拒绝 v2 项目表单', () => {
        expect(() => normalizePlayerSchema({ schema_version: 2, groups: [] })).toThrow('版本不受支持')
    })

    it('拒绝旧控件类型，不再静默迁移', () => {
        expect(() => normalizePlayerSchema({
            groups: [{ fields: [{ target: '$ctx.window', ui_type: 'string', default: '' }] }]
        })).toThrow('不支持的 Player 控件类型')
    })

    it('对 Player 启动参数执行必填、范围与正则校验', () => {
        const schema = {
            groups: [{
                fields: [
                    { label: '次数', target: '$var.count', ui_type: 'number', default: 3, min: 1, max: 5 },
                    { label: '账号', target: '$ctx.account', ui_type: 'str', required: true, pattern: '[a-z]+' }
                ]
            }]
        }
        const config = buildPlayerConfig(schema)
        expect(validatePlayerConfig(schema, config)[0].message).toBe('账号 为必填项')

        config.ctx.account = 'ABC'
        expect(validatePlayerConfig(schema, config)[0].message).toBe('账号 格式不正确')
    })

    it('静态选项统一为 label/value 对象', () => {
        const schema = normalizePlayerSchema({
            groups: [{ fields: [{ target: '$var.mode', ui_type: 'select', options: ['A', { label: '乙', value: 'B' }] }] }]
        })
        expect(schema.groups[0].fields[0].options).toEqual([
            { label: 'A', value: 'A' },
            { label: '乙', value: 'B' }
        ])
    })

    it('项目设置和节点属性进入隔离的运行覆盖槽位', () => {
        const schema = {
            groups: [{ fields: [
                { target: '$settings.max_logs', ui_type: 'number', default: 800 },
                { target: '$node.node_a.params.image_source', ui_type: 'image_asset', default: 'asset://demo' }
            ] }]
        }
        const config = buildPlayerConfig(schema)
        expect(config.overrides).toEqual({
            '$settings.max_logs': 800,
            '$node.node_a.params.image_source': 'asset://demo'
        })
        expect(validatePlayerConfig(schema, config)).toEqual([])
    })
})
