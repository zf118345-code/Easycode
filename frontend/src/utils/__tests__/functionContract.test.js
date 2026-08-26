import { describe, expect, it } from 'vitest'
import { containsScopedReference, formatScopedReference, rewriteScopedReferences } from '@/utils/functionContract'

describe('functionContract', () => {
    it('中文契约名使用花括号，标识符使用点号', () => {
        expect(formatScopedReference('param', 'amount')).toBe('$param.amount')
        expect(formatScopedReference('local', '临时结果')).toBe('$local{临时结果}')
    })

    it('重命名会递归更新点号与花括号引用', () => {
        const value = {
            expression: '$param.amount + 1',
            nested: ['$param{amount}', { target: '$local.keep' }]
        }
        expect(rewriteScopedReferences(value, 'param', 'amount', '起始值')).toEqual({
            expression: '$param{起始值} + 1',
            nested: ['$param{起始值}', { target: '$local.keep' }]
        })
        expect(containsScopedReference(value, 'param', 'amount')).toBe(true)
        expect(containsScopedReference(value, 'local', 'missing')).toBe(false)
    })
})
