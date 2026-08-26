import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ControlGesturePathEditor from '../ControlGesturePathEditor.vue'

describe('ControlGesturePathEditor', () => {
    let pinia

    beforeEach(() => {
        pinia = createPinia()
        setActivePinia(pinia)
    })

    it('保留显式的 0ms 移动时长，不会偷偷改回默认 300ms', () => {
        const wrapper = mount(ControlGesturePathEditor, {
            props: {
                config: { min_points: 2, max_points: 32 },
                modelValue: [
                    { position: [10, 20], move_ms: 0, hold_ms: 0 },
                    { position: [30, 40], move_ms: 0, hold_ms: 0 }
                ],
                context: { action: 'drag' }
            },
            global: { plugins: [pinia] }
        })

        expect(wrapper.vm.points[1].move_ms).toBe(0)
        wrapper.vm.updateField(1, 'move_ms', 0)
        expect(wrapper.emitted('update:modelValue').at(-1)[0][1].move_ms).toBe(0)
    })
})
