import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'

import CanvasEdgeLayer from '../CanvasEdgeLayer.vue'

describe('CanvasEdgeLayer', () => {
    const baseProps = {
        viewport: { x: 0, y: 0, zoom: 1 },
        containerSize: { width: 600, height: 400 },
        edges: [
            {
                id: 'edge_a',
                path: 'M 0 20 L 200 20',
                markerUrl: 'url(#arrow-succ-right)',
                executing: true,
                focusState: 'boundary',
                jumpArcs: [{
                    gapPath: 'M 90 20 L 110 20',
                    bridgePath: 'M 94 20 Q 100 14 106 20',
                }],
                waypoints: [{ id: 'w1', x: 100, y: 20 }],
            },
            {
                id: 'edge_b',
                path: 'M 0 80 L 200 80',
                markerUrl: 'url(#arrow-succ-right)',
                dimmed: true,
                focusState: 'dimmed',
            },
        ],
        editingEdgeId: 'edge_a',
    }

    it('只为执行边播放动画，并绘制跨线桥和转接点', () => {
        const wrapper = mount(CanvasEdgeLayer, { props: baseProps })

        expect(wrapper.findAll('.edge-flow-path')).toHaveLength(1)
        expect(wrapper.findAll('.edge-jump-gap')).toHaveLength(1)
        expect(wrapper.findAll('.edge-jump-bridge')).toHaveLength(1)
        expect(wrapper.findAll('.edge-waypoint')).toHaveLength(1)
        expect(wrapper.findAll('.edge-group')[1].classes()).toContain('is-dimmed')
    })

    it('把双击、右键、悬停和转接点拖动事件交给画布控制器', async () => {
        const wrapper = mount(CanvasEdgeLayer, { props: baseProps })
        const hit = wrapper.find('.edge-hit-area')
        await hit.trigger('mouseenter')
        await hit.trigger('dblclick')
        await hit.trigger('contextmenu')
        await wrapper.find('.edge-waypoint').trigger('focus')
        await wrapper.find('.edge-waypoint').trigger('mousedown')

        expect(wrapper.emitted('edge-hover')).toHaveLength(1)
        expect(wrapper.emitted('edge-double-click')).toHaveLength(1)
        expect(wrapper.emitted('edge-contextmenu')).toHaveLength(1)
        expect(wrapper.emitted('waypoint-focus')).toHaveLength(1)
        expect(wrapper.emitted('waypoint-mousedown')).toHaveLength(1)
    })
})
