import { describe, expect, it } from 'vitest'
import { getLogCategory, getLogLevel, getLogText, isLogInFilter, normalizeLogItem } from '../logModel'

describe('日志视图模型', () => {
    it.each([
        ['[页面状态] 已定位当前页面', 'vision'],
        ['[智能跳转] 寻路成功', 'navigation'],
        ['[目标绑定] 已绑定窗口', 'operation'],
        ['[变量操作] count = 2', 'data'],
        ['[Node 执行] 等待节点', 'node'],
        ['[Executor] 启动流程', 'execution']
    ])('为旧文本日志推断稳定分类：%s', (message, expected) => {
        expect(getLogCategory({ message })).toBe(expected)
    })

    it('以后端显式分类为准并支持跨分类问题筛选', () => {
        const log = normalizeLogItem({ category: 'vision', level: 'warning', message: '⚠️ 未找到模板' })
        expect(log.category).toBe('vision')
        expect(log.level).toBe('warning')
        expect(isLogInFilter(log, 'vision')).toBe(true)
        expect(isLogInFilter(log, 'issues')).toBe(true)
    })

    it('清理装饰 Emoji 但保留真正的日志内容', () => {
        expect(getLogText({ message: '✅ [Node 完成] 成功' })).toBe('[Node 完成] 成功')
        expect(getLogLevel({ message: '❌ 点击失败' })).toBe('error')
    })
})
