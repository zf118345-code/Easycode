import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'

import VNextValueControl from '../components/VNextValueControl.vue'


describe('VNextValueControl strong capture values', () => {
    it('颜色使用共享 RGBA 编辑器而不是暴露 JSON', async () => {
        const wrapper = mount(VNextValueControl, {
            props: {
                controlType: 'color',
                valueType: 'color',
                label: '目标颜色',
                modelValue: { red: 18, green: 52, blue: 86, alpha: 200 },
            },
        })

        expect(wrapper.find('textarea').exists()).toBe(false)
        expect(wrapper.get<HTMLInputElement>('.color-hex').element.value).toBe('#123456')
        expect(wrapper.get<HTMLInputElement>('.color-swatch').element.value).toBe('#123456')
        await wrapper.get('.color-swatch').setValue('#ff6600')
        expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual({
            'color.field.red': 255, 'color.field.green': 102,
            'color.field.blue': 0, 'color.field.alpha': 200,
        })
        await wrapper.get('.color-alpha input').setValue('128')
        await wrapper.get('.color-alpha input').trigger('change')
        expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual({
            'color.field.red': 18, 'color.field.green': 52,
            'color.field.blue': 86, 'color.field.alpha': 128,
        })
    })

    it('颜色控件读取规范字段并把取色作为同一行的专用动作', async () => {
        const wrapper = mount(VNextValueControl, {
            props: {
                controlType: 'color',
                valueType: 'color',
                label: '目标颜色',
                modelValue: {
                    'color.field.red': 97,
                    'color.field.green': 98,
                    'color.field.blue': 100,
                    'color.field.alpha': 255,
                },
                actions: [{ id: 'pick-color', capture_kind: 'color', platforms: ['windows'] }],
            },
        })

        expect(wrapper.get<HTMLInputElement>('.color-hex').element.value).toBe('#616264')
        expect(wrapper.text()).not.toContain('color.field.red')
        const action = wrapper.get<HTMLButtonElement>('button[aria-label="从目标画面取色"]')
        await action.trigger('click')
        expect(wrapper.emitted('action')?.[0]?.[0]).toMatchObject({ id: 'pick-color', capture_kind: 'color' })
    })

    it('可选数字保持为空，清空后也不会被改写成 0', async () => {
        const wrapper = mount(VNextValueControl, {
            props: { controlType: 'number', modelValue: null },
        })

        const input = wrapper.get<HTMLInputElement>('input[type="number"]')
        expect(input.element.value).toBe('')
        await input.setValue('18')
        await input.trigger('change')
        await input.setValue('')
        await input.trigger('change')
        expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toBeNull()
    })

    it('可选时长保持为空，单独切换单位不会凭空生成 0', async () => {
        const wrapper = mount(VNextValueControl, {
            props: { controlType: 'duration', modelValue: null },
        })

        expect(wrapper.get<HTMLInputElement>('input[type="number"]').element.value).toBe('')
        await wrapper.get('select').setValue('s')
        expect(wrapper.emitted('update:modelValue')).toBeUndefined()
    })

    it('控件选择器只显示稳定摘要，不暴露可编辑 selector 或 JSON', () => {
        const wrapper = mount(VNextValueControl, {
            props: {
                controlType: 'control-selector',
                modelValue: {
                    'control_selector.field.name': '登录按钮',
                    'control_selector.field.automation_id': 'login-button',
                    'control_selector.field.ancestor_path': [{ name: '游戏窗口' }],
                },
                actions: [{ id: 'capture-control', platforms: ['windows'] }],
            },
        })

        expect(wrapper.text()).toContain('登录按钮')
        expect(wrapper.text()).toContain('login-button')
        expect(wrapper.text()).not.toContain('control_selector.field')
        expect(wrapper.find('textarea').exists()).toBe(false)
        expect(wrapper.get('button').attributes('aria-label')).toBe('捕获控件')
    })

    it('窗口绑定显示可读窗口身份，并提供同一套图标捕获动作', () => {
        const wrapper = mount(VNextValueControl, {
            props: {
                controlType: 'control-selector',
                valueType: 'optional<window_binding>',
                modelValue: {
                    binding_version: 1,
                    binding_id: 'window_binding_one',
                    title: '超能世界',
                    class_name: 'Chrome_WidgetWin_1',
                    executable_name: 'WeChatAppEx.exe',
                    hwnd: 101,
                    process_id: 202,
                    process_started_at_ms: 303,
                    captured_at: '2026-09-09T00:00:00+0800',
                },
                actions: [{ id: 'capture-window', platforms: ['windows'] }],
            },
        })

        expect(wrapper.text()).toContain('超能世界')
        expect(wrapper.text()).toContain('WeChatAppEx.exe')
        expect(wrapper.text()).not.toContain('window_binding_one')
        expect(wrapper.find('textarea').exists()).toBe(false)
        expect(wrapper.get('button').attributes('aria-label')).toBe('捕获窗口')
    })

    it('手势路径显示点数并保持只能通过采集动作替换', async () => {
        const wrapper = mount(VNextValueControl, {
            props: {
                controlType: 'gesture-path',
                modelValue: [[10, 20], [30, 40], [50, 60]],
                actions: [{ id: 'capture-path', platforms: ['windows'] }],
            },
        })

        expect(wrapper.text()).toContain('已记录 3 个路径点')
        expect(wrapper.find('textarea').exists()).toBe(false)
        await wrapper.get('button').trigger('click')
        expect(wrapper.emitted('action')?.[0]?.[0]).toMatchObject({ id: 'capture-path' })
    })

    it('字符串到布尔值字典显示为固定复选清单，并保留未修改项', async () => {
        const wrapper = mount(VNextValueControl, {
            props: {
                controlType: 'key-value',
                valueType: 'map<string,bool>',
                modelValue: {
                    '使用5次点金手': true,
                    '完成3次传奇决斗场战斗': false,
                },
                options: [
                    { label: '传奇决斗场', value: '完成3次传奇决斗场战斗' },
                    { label: '点金手', value: '使用5次点金手' },
                ],
            },
        })

        expect(wrapper.find('textarea').exists()).toBe(false)
        const choices = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
        expect(choices).toHaveLength(2)
        expect(choices.map(item => item.attributes('aria-label'))).toEqual([
            '完成3次传奇决斗场战斗',
            '使用5次点金手',
        ])
        expect(wrapper.text()).toContain('使用5次点金手')
        expect(wrapper.findAll('label').map(item => item.text())).toEqual([
            '完成3次传奇决斗场战斗',
            '使用5次点金手',
        ])
        await choices[0].setValue(true)
        expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual({
            '使用5次点金手': true,
            '完成3次传奇决斗场战斗': true,
        })
    })

    it('固定布尔选项显示锁定语义且不能被交互改写', async () => {
        const wrapper = mount(VNextValueControl, {
            props: {
                controlType: 'key-value',
                valueType: 'map<string,bool>',
                modelValue: { '暂未开放': true, '必须执行': false, '用户决定': false },
                options: [
                    { label: '暂未开放', value: '暂未开放', fixed_value: false, fixed_reason: '当前版本暂未开放' },
                    { label: '必须执行', value: '必须执行', fixed_value: true },
                    { label: '用户决定', value: '用户决定' },
                ],
            },
        })

        const choices = wrapper.findAll<HTMLInputElement>('input[type="checkbox"]')
        expect(choices[0].element.checked).toBe(false)
        expect(choices[0].element.disabled).toBe(true)
        expect(choices[0].attributes('aria-label')).toContain('固定不可选')
        expect(choices[1].element.checked).toBe(true)
        expect(choices[1].element.disabled).toBe(true)
        expect(wrapper.text()).toContain('必选')
        expect(wrapper.text()).toContain('不可选')
        await choices[0].trigger('change')
        expect(wrapper.emitted('update:modelValue')).toBeUndefined()
        await choices[2].setValue(true)
        expect(wrapper.emitted('update:modelValue')?.at(-1)?.[0]).toEqual({
            '暂未开放': false,
            '必须执行': true,
            '用户决定': true,
        })
    })
})
