import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import VariableAwareInput from '../VariableAwareInput.vue'

/**
 * VariableAwareInput 交互测试：
 * 1. 失焦态：完整 token 渲染为发光 chip（显示 name、data-token 存原文、无空格污染）
 * 2. 聚焦：chip 展开为 $var{name} 纯文本（可编辑）
 * 3. 点击 chip：展开并定位到 token 内
 * 4. 输入 → 失焦：chip 化；值往返保持原文（回归：点击进入不再出现 undefined/多余空格）
 * 5. 多 token / 编辑后修改 token
 */

function makeWrapper(modelValue = '') {
    // attachTo document.body：jsdom 中未挂载的元素不会派发 focus/blur 事件
    return mount(VariableAwareInput, {
        props: {
            config: { type: 'str', label: '测试' },
            modelValue
        },
        attachTo: document.body
    })
}

/** 触发 contenteditable 的 input 事件（模拟用户输入） */
function fireInput(wrapper, text) {
    const el = wrapper.element
    el.textContent = text
    el.dispatchEvent(new Event('input', { bubbles: true }))
}

describe('VariableAwareInput', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
    })

    afterEach(() => {
        document.body.innerHTML = ''
    })

    it('无值显示空态（placeholder 样式类）', () => {
        const wrapper = makeWrapper('')
        expect(wrapper.classes()).toContain('is-empty')
        expect(wrapper.element.textContent).toBe('')
    })

    it('失焦态：完整 token 渲染为发光 chip（显示 name、data-token 存原文）', () => {
        const wrapper = makeWrapper('$var{coin}')
        const chip = wrapper.element.querySelector('.var-chip')
        expect(chip).not.toBeNull()
        expect(chip.textContent).toBe('coin')
        expect(chip.dataset.token).toBe('$var{coin}')
        // 值无空格污染：textContent 就是 coin
        expect(wrapper.element.textContent).toBe('coin')
    })

    it('聚焦：chip 展开为 $var{name} 纯文本（可编辑、无空格）', () => {
        const wrapper = makeWrapper('$var{coin}')
        wrapper.element.focus()
        expect(wrapper.element.querySelector('.var-chip')).toBeNull()
        // 原文展开，无多余空格（回归 undefined/污染问题）
        expect(wrapper.element.textContent).toBe('$var{coin}')
    })

    it('聚焦展开 → 失焦恢复 chip → 再聚焦：值往返保持原文', () => {
        const wrapper = makeWrapper('$var{coin}')
        // 第一轮：聚焦展开 → 失焦 chip 化
        wrapper.element.focus()
        expect(wrapper.element.textContent).toBe('$var{coin}')
        wrapper.element.blur()
        expect(wrapper.element.querySelector('.var-chip')).not.toBeNull()
        // 第二轮：再次聚焦 → 原文展开（无空格、无 undefined）
        wrapper.element.focus()
        expect(wrapper.element.textContent).toBe('$var{coin}')
    })

    it('点击 chip：展开为 $var{name} 可编辑', () => {
        const wrapper = makeWrapper('$var{coin}')
        const chip = wrapper.element.querySelector('.var-chip')
        chip.dispatchEvent(new MouseEvent('click', { bubbles: true }))
        expect(wrapper.element.querySelector('.var-chip')).toBeNull()
        expect(wrapper.element.textContent).toBe('$var{coin}')
    })

    it('输入 $var{coin} 后失焦：chip 化；值原文提交', async () => {
        const wrapper = makeWrapper('')
        wrapper.element.focus()
        fireInput(wrapper, '$var{coin}')
        // input 事件提交原文（无空格）
        expect(wrapper.emitted('update:modelValue')).toBeTruthy()
        const emitted = wrapper.emitted('update:modelValue').at(-1)[0]
        expect(emitted).toBe('$var{coin}')
        // 失焦 → chip 化
        wrapper.element.blur()
        const chip = wrapper.element.querySelector('.var-chip')
        expect(chip).not.toBeNull()
        expect(chip.textContent).toBe('coin')
        expect(chip.dataset.token).toBe('$var{coin}')
    })

    it('多 token 混合文本：只 chip 化完整 token', () => {
        const wrapper = makeWrapper('a $var{x} b $ctx{y} c')
        const chips = wrapper.element.querySelectorAll('.var-chip')
        expect(chips.length).toBe(2)
        expect(chips[0].dataset.token).toBe('$var{x}')
        expect(chips[1].dataset.token).toBe('$ctx{y}')
        // 展开后原文完整
        wrapper.element.focus()
        expect(wrapper.element.textContent).toBe('a $var{x} b $ctx{y} c')
    })

    it('编辑态修改 token 后失焦：按新内容 chip 化', () => {
        const wrapper = makeWrapper('$var{coin}')
        wrapper.element.focus()
        fireInput(wrapper, '$var{coin2}')
        wrapper.element.blur()
        const chip = wrapper.element.querySelector('.var-chip')
        expect(chip).not.toBeNull()
        expect(chip.textContent).toBe('coin2')
        expect(chip.dataset.token).toBe('$var{coin2}')
    })

    it('不完整 token（$var{co）不 chip 化，保持文本', () => {
        const wrapper = makeWrapper('$var{co')
        expect(wrapper.element.querySelector('.var-chip')).toBeNull()
        expect(wrapper.element.textContent).toBe('$var{co')
    })

    it('外部更新（撤销/重置）同步 DOM', async () => {
        const wrapper = makeWrapper('$var{coin}')
        await wrapper.setProps({ modelValue: '$var{newone}' })
        const chip = wrapper.element.querySelector('.var-chip')
        expect(chip).not.toBeNull()
        expect(chip.dataset.token).toBe('$var{newone}')
        expect(chip.textContent).toBe('newone')
    })
})
