import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import CanvasContextMenu from '../CanvasContextMenu.vue'

const hiddenSpawnMenu = { visible: false, x: 0, y: 0, sourceNodeId: null }

describe('CanvasContextMenu 键盘操作', () => {
    it('打开后聚焦首个可用项，方向键循环，Escape 关闭', async () => {
        const wrapper = mount(CanvasContextMenu, {
            attachTo: document.body,
            props: {
                spawnMenu: hiddenSpawnMenu,
                contextMenu: { visible: false, x: 10, y: 10, targetType: 'canvas_public' },
                hasClipboard: true
            }
        })

        await wrapper.setProps({
            contextMenu: { visible: true, x: 10, y: 10, targetType: 'canvas_public' }
        })
        await nextTick()

        const items = wrapper.findAll('[role="menuitem"]')
        expect(items).toHaveLength(3)
        expect(document.activeElement).toBe(items[0].element)

        await wrapper.find('[role="menu"]').trigger('keydown', { key: 'ArrowDown' })
        expect(document.activeElement).toBe(items[1].element)
        await wrapper.find('[role="menu"]').trigger('keydown', { key: 'ArrowDown' })
        expect(document.activeElement).toBe(items[2].element)

        await wrapper.find('[role="menu"]').trigger('keydown', { key: 'Escape' })
        expect(wrapper.emitted('dismiss')).toHaveLength(1)
        wrapper.unmount()
    })
})
