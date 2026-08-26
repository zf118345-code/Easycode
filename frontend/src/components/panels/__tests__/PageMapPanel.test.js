import { beforeEach, describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PageMapPanel from '../PageMapPanel.vue'
import { useProjectStore } from '@/stores'

describe('PageMapPanel 页面地图侧栏', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        const store = useProjectStore()
        store.blueprint = {
            page_map: {
                nodes: [
                    { node_id: 'page_1', node_name: '登录页', node_type: 'page_state', params: { features: [{}] } },
                    { node_id: 'click_1', node_name: '点击登录', node_type: 'click', params: {} }
                ],
                edges: []
            }
        }
    })

    it('不重复渲染页面地图标题，并在节点右侧显示中文类型', () => {
        const wrapper = mount(PageMapPanel)
        expect(wrapper.find('.open-map').exists()).toBe(false)
        expect(wrapper.findAll('.page-row')).toHaveLength(2)
        const labels = wrapper.findAll('.page-row small').map(item => item.text())
        expect(labels).toEqual(['页面状态', '鼠标点击'])
        wrapper.unmount()
    })
})
