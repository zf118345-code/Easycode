// frontend/src/utils/__tests__/captureNode.test.js
// 控件捕获 → 控件节点参数推导（G 环节纯函数）
import { describe, it, expect } from 'vitest'
import { buildControlParamsFromInfo, buildControlNodeName, formatControlInfo } from '../captureNode'

describe('buildControlParamsFromInfo 捕获信息 → 节点查找参数', () => {
    it('name 优先', () => {
        expect(buildControlParamsFromInfo({ name: '确定', control_type: 'button' }))
            .toEqual({ by: 'uia_name', target: '确定' })
    })
    it('无 name 时回退 type → id → class', () => {
        expect(buildControlParamsFromInfo({ control_type: 'button' }))
            .toEqual({ by: 'uia_type', target: 'button' })
        expect(buildControlParamsFromInfo({ automation_id: 'e1' }))
            .toEqual({ by: 'uia_id', target: 'e1' })
        expect(buildControlParamsFromInfo({ class_name: 'Button' }))
            .toEqual({ by: 'uia_class', target: 'Button' })
    })
    it('无效输入返回空 target', () => {
        expect(buildControlParamsFromInfo({})).toEqual({ by: 'uia_name', target: '' })
        expect(buildControlParamsFromInfo(null)).toEqual({ by: 'uia_name', target: '' })
        expect(buildControlParamsFromInfo(undefined)).toEqual({ by: 'uia_name', target: '' })
    })
    it('name 前后空白裁剪', () => {
        expect(buildControlParamsFromInfo({ name: '  确定  ' })).toEqual({ by: 'uia_name', target: '确定' })
    })
})

describe('buildControlNodeName 节点名', () => {
    it('控件_名称 截断 12 字符', () => {
        expect(buildControlNodeName({ name: '确定' })).toBe('控件_确定')
        // '这是一个非常非常长的按钮名称' 14 字符 → 截断为 12 字符
        expect(buildControlNodeName({ name: '这是一个非常非常长的按钮名称' }))
            .toBe('控件_这是一个非常非常长的按钮')
    })
    it('无名称回退类型/未命名', () => {
        expect(buildControlNodeName({ control_type: 'button' })).toBe('控件_button')
        expect(buildControlNodeName({})).toBe('控件_未命名')
        expect(buildControlNodeName(null)).toBe('控件_未命名')
    })
})

describe('formatControlInfo 控件信息分行展示（只读 textarea）', () => {
    it('UIA 信息全字段分行展示', () => {
        const text = formatControlInfo({
            name: '确定', control_type: 'button', automation_id: 'btn_1',
            class_name: 'Button', window_title: '主窗口', rect: [10, 20, 30, 40]
        })
        expect(text.split('\n')).toEqual([
            '控件名称：确定',
            '控件类型：button',
            '自动化ID：btn_1',
            '类名：Button',
            '窗口标题：主窗口',
            '坐标：[10, 20, 30, 40]'
        ])
    })
    it('兼容 Win32 字段（text/句柄/嵌套顶层窗口）', () => {
        const text = formatControlInfo({
            text: '确定', control_type: 'button', class_name: 'Button',
            hwnd: 12345, rect: [0, 0, 50, 20],
            top_level_window: { text: '主窗口' }
        })
        expect(text).toContain('控件名称：确定')
        expect(text).toContain('句柄：12345')
        expect(text).toContain('窗口标题：主窗口')
    })
    it('空字段跳过，无 control_info 时兜底显示控件名称', () => {
        expect(formatControlInfo({ name: '确定', control_type: '' })).toBe('控件名称：确定')
        expect(formatControlInfo(null, '开始游戏')).toBe('控件名称：开始游戏')
        expect(formatControlInfo({}, '开始游戏')).toBe('控件名称：开始游戏')
        expect(formatControlInfo({})).toBe('')
    })
    it('可用状态展示', () => {
        const text = formatControlInfo({ name: 'x', is_enabled: true })
        expect(text).toContain('可用状态：可用')
        expect(formatControlInfo({ name: 'x', is_enabled: false })).toContain('可用状态：禁用')
    })
})
