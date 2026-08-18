// frontend/src/components/__tests__/ParamRendererControl.test.js
// C 环节：ParamRenderer 真实渲染 control 节点 schema
//   - by select：可展开且含 7 个查找方式选项（uia_* 优先）
//   - target 输入框：值展示与更新事件
//   - index：help 图标渲染
//   - visible_if：text_input / save_to_var 按 action 显隐
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { nextTick } from 'vue'
import ElementPlus from 'element-plus'
import ParamRenderer from '../ParamRenderer.vue'
import { CONTROL_SCHEMA } from '@/testFixtures/controlSchema'

// jsdom 缺少的浏览器 API（element-plus popper/尺寸监听依赖）
globalThis.ResizeObserver = globalThis.ResizeObserver || class { observe() {} unobserve() {} disconnect() {} }

function mountParam(config, value, context = {}) {
    return mount(ParamRenderer, {
        props: {
            config,
            value,
            label: config.label || '',
            context
        },
        attachTo: document.body,
        global: {
            plugins: [createPinia(), ElementPlus],
            stubs: {
                FileBrowser: true,
                ScreenshotTool: true,
                ConditionDialog: true,
                'el-dialog': true
            }
        }
    })
}

/** 展开 el-select 下拉，返回菜单项文本列表 */
async function openSelectOptions(wrapper) {
    await wrapper.find('.el-select').trigger('click')
    await nextTick()
    await nextTick()
    await nextTick()
    return [...document.querySelectorAll('.el-select-dropdown__item')].map(el => el.textContent.trim())
}

describe('ParamRenderer × control schema：by 查找方式 select', () => {
    it('渲染标签 + select，展开含全部 7 个查找方式', async () => {
        document.body.innerHTML = ''
        const wrapper = mountParam(CONTROL_SCHEMA.params.by, 'uia_name')

        expect(wrapper.text()).toContain('查找方式')
        expect(wrapper.find('.el-select').exists()).toBe(true)

        const options = await openSelectOptions(wrapper)
        expect(options).toHaveLength(7)
        expect(options[0]).toContain('uia_name')   // uia_* 优先
        expect(options.join('|')).toContain('uia_type')
        expect(options.join('|')).toContain('control_type')
        wrapper.unmount()
    })
})

describe('ParamRenderer × control schema：target 输入框', () => {
    it('渲染 VariableAwareInput 并展示当前值（纯文本 + 变量 chip）', () => {
        document.body.innerHTML = ''
        const wrapper = mountParam(CONTROL_SCHEMA.params.target, '确定')
        expect(wrapper.text()).toContain('控件标识')
        const input = wrapper.find('.var-aware-input')
        expect(input.exists()).toBe(true)
        expect(input.element.textContent).toBe('确定')

        // 变量 token：失焦态渲染为发光 chip（显示 name、data-token 存原文）
        document.body.innerHTML = ''
        const w2 = mountParam(CONTROL_SCHEMA.params.target, '$var{btn_text}')
        const chip = w2.find('.var-chip')
        expect(chip.exists()).toBe(true)
        expect(chip.text()).toBe('btn_text')
        expect(chip.attributes('data-token')).toBe('$var{btn_text}')
        w2.unmount()
        wrapper.unmount()
    })

    it('输入 → emit update（值回写节点 params）', async () => {
        document.body.innerHTML = ''
        const wrapper = mountParam(CONTROL_SCHEMA.params.target, '')
        const input = wrapper.find('.var-aware-input')
        await input.trigger('focus')
        input.element.textContent = '开始游戏'
        input.element.dispatchEvent(new Event('input', { bubbles: true }))
        const updates = wrapper.emitted('update')
        expect(updates).toBeTruthy()
        expect(updates.at(-1)[0]).toBe('开始游戏')
        wrapper.unmount()
    })
})

describe('ParamRenderer × control schema：index help 图标', () => {
    it('index 有 help 配置 → 渲染「?」帮助图标', () => {
        document.body.innerHTML = ''
        const wrapper = mountParam(CONTROL_SCHEMA.params.index, 0)
        expect(wrapper.text()).toContain('匹配序号')
        expect(wrapper.find('.param-help-icon').exists()).toBe(true)
        wrapper.unmount()
    })
})

describe('ParamRenderer × control schema：visible_if 显隐', () => {
    it('action=click 时隐藏 text_input / save_to_var', () => {
        document.body.innerHTML = ''
        const ctx = { action: 'click' }
        const t = mountParam(CONTROL_SCHEMA.params.text_input, '', ctx)
        const s = mountParam(CONTROL_SCHEMA.params.save_to_var, '', ctx)
        expect(t.text()).not.toContain('输入内容')
        expect(s.text()).not.toContain('保存结果到变量')
        t.unmount(); s.unmount()
    })

    it('action=input_text 时显示 text_input；action=exists 时显示 save_to_var', () => {
        document.body.innerHTML = ''
        const t = mountParam(CONTROL_SCHEMA.params.text_input, '', { action: 'input_text' })
        expect(t.text()).toContain('输入内容')
        const s = mountParam(CONTROL_SCHEMA.params.save_to_var, '', { action: 'exists' })
        expect(s.text()).toContain('保存结果到变量')
        t.unmount(); s.unmount()
    })
})
