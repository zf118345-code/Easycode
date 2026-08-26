// frontend/src/components/inspector/panels/__tests__/NodeInspectorPanelControl.test.js
// C 环节：NodeInspectorPanel 遍历渲染 control 节点 schema
//   - 每个参数（action/by/target/window_title/index/text_input/save_to_var/timeout）都渲染出对应 ParamRenderer
//   - config 透传正确（type/label/default）
//   - 参数更新 → emit save
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import NodeInspectorPanel from '../NodeInspectorPanel.vue'
import { useProjectStore } from '@/stores'
import { CONTROL_SCHEMA } from '@/testFixtures/controlSchema'
import { buildNodeDefaultParams } from '@/utils/nodeDefaults'
import { visionApi } from '@/api/visionApi'

globalThis.ResizeObserver = globalThis.ResizeObserver || class { observe() {} unobserve() {} disconnect() {} }

// ParamRenderer stub：渲染 label|type 供遍历断言，支持 update 事件回传
const ParamRendererStub = {
    name: 'ParamRenderer',
    props: ['config', 'value', 'label', 'context'],
    emits: ['update', 'autoChangeType'],
    template: '<div class="pr-stub">{{ label }}|{{ config.type }}|{{ JSON.stringify(config) }}</div>'
}
const ElInputStub = {
    inheritAttrs: false,
    props: ['modelValue', 'size'],
    emits: ['update:modelValue', 'change'],
    template: '<input :value="modelValue" />'
}
const ElButtonStub = {
    inheritAttrs: false,
    props: ['disabled'],
    emits: ['click'],
    template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>'
}

function makeNode() {
    const params = buildNodeDefaultParams('control', { control: CONTROL_SCHEMA })
    return {
        node_id: 'ctrl_1',
        node_name: '我的控件节点',
        node_type: 'control',
        params: { ...params, target: '开始游戏' },
        delay_before: 200,
        loop_count: 1
    }
}

function mountPanel(node = makeNode()) {
    return mount(NodeInspectorPanel, {
        props: { node },
        attachTo: document.body,
        global: {
            stubs: {
                ParamRenderer: ParamRendererStub,
                'el-dialog': true,
                'el-tooltip': true,
                'el-input': ElInputStub,
                'el-button': ElButtonStub,
                'el-slider': true
            }
        }
    })
}

describe('NodeInspectorPanel × control 节点', () => {
    beforeEach(() => {
        document.body.innerHTML = ''
        setActivePinia(createPinia())
        useProjectStore().paramsDefinitions = { control: CONTROL_SCHEMA }
    })

    afterEach(() => {
        vi.restoreAllMocks()
    })

    it('遍历渲染全部 8 个参数（含 visible_if 依赖的 text_input/save_to_var）', () => {
        const wrapper = mountPanel()
        const stubs = wrapper.findAll('.pr-stub').map(w => w.text())
        expect(stubs).toHaveLength(8)
        for (const label of ['操作方式', '查找方式', '控件标识', '目标窗口标题', '匹配序号', '输入内容', '保存结果到变量', '查找超时时长']) {
            expect(stubs.some(t => t.startsWith(label))).toBe(true)
        }
        wrapper.unmount()
    })

    it('config 透传：by 的 options 含 7 项且 default=uia_name；timeout default=3000', () => {
        const wrapper = mountPanel()
        const byStub = wrapper.findAll('.pr-stub').find(w => w.text().startsWith('查找方式'))
        const byConfig = JSON.parse(byStub.text().split('|')[2])
        expect(byConfig.options).toHaveLength(7)
        expect(byConfig.default).toBe('uia_name')
        expect(byConfig.options[0].value).toBe('uia_name')

        const timeoutStub = wrapper.findAll('.pr-stub').find(w => w.text().startsWith('查找超时时长'))
        expect(JSON.parse(timeoutStub.text().split('|')[2]).default).toBe(3000)
        wrapper.unmount()
    })

    it('stub 更新参数 → handleParamUpdate 写回 node.params 并 emit save', async () => {
        const node = makeNode()
        const wrapper = mountPanel(node)
        const targetStub = wrapper.findAllComponents(ParamRendererStub)
            .find(w => w.text().startsWith('控件标识'))
        targetStub.vm.$emit('update', '关闭按钮')

        expect(node.params.target).toBe('关闭按钮')
        expect(wrapper.emitted('save')).toBeTruthy()
        wrapper.unmount()
    })

    it('录制区域为空时从图片资源元数据回填并保存显示值', async () => {
        const store = useProjectStore()
        store.currentProjectPath = 'D:/project'
        store.paramsDefinitions = {
            image_recognition: {
                label: '图像识别',
                params: {
                    image_source: { type: 'file', label: '模板图片' },
                    region_type: { type: 'select', label: '匹配区域' },
                    region_value: { type: 'list_int4_picker', label: '匹配区域坐标' },
                    region_reference_size: { type: 'list_int2', hidden: true }
                }
            }
        }
        vi.spyOn(visionApi, 'resolveTemplate').mockResolvedValue({
            capture: {
                region: [16, 266, 58, 79],
                reference_size: [960, 540],
                coordinate_space: 'workspace_px'
            }
        })
        const node = {
            node_id: 'image_1',
            node_name: '图像识别节点',
            node_type: 'image_recognition',
            params: {
                image_source: 'asset://button',
                region_type: 'recorded',
                region_value: [0, 0, 0, 0],
                region_reference_size: [0, 0]
            },
            delay_before: 0,
            loop_count: 1
        }

        const wrapper = mountPanel(node)
        await flushPromises()

        expect(node.params.region_value).toEqual([16, 266, 58, 79])
        expect(node.params.region_reference_size).toEqual([960, 540])
        expect(wrapper.emitted('save')).toBeTruthy()
        wrapper.unmount()
    })

    it('OCR 预览仅在已有模板且换图、提交灰度参数或手动刷新时请求', async () => {
        vi.useFakeTimers()
        try {
            const store = useProjectStore()
            store.currentProjectPath = 'D:/project'
            store.paramsDefinitions = {
                ocr_recognition: {
                    label: 'OCR 文字识别',
                    params: {
                        image_source: { type: 'file', label: 'OCR 模板图片' },
                        gray_scale: { type: 'bool', label: '灰度处理' },
                        gray_threshold: { type: 'int', label: '二值化灰度阈值' }
                    }
                }
            }
            const testOcr = vi.spyOn(visionApi, 'testOcr').mockResolvedValue({ text: '登录成功' })
            const node = {
                node_id: 'ocr_1', node_name: 'OCR 识别节点', node_type: 'ocr_recognition',
                params: { image_source: '', gray_scale: true, gray_threshold: 127 },
                delay_before: 0, loop_count: 1
            }
            const wrapper = mountPanel(node)
            await flushPromises()
            expect(testOcr).not.toHaveBeenCalled()
            expect(wrapper.text()).toContain('选择模板图片后可测试识别')

            const imageField = wrapper.findAllComponents(ParamRendererStub)
                .find(item => item.text().startsWith('OCR 模板图片'))
            imageField.vm.$emit('update', 'asset://ocr_login')
            await vi.advanceTimersByTimeAsync(220)
            await flushPromises()
            expect(testOcr).toHaveBeenCalledTimes(1)

            const grayField = wrapper.findAllComponents(ParamRendererStub)
                .find(item => item.text().startsWith('灰度处理'))
            grayField.vm.$emit('update', false)
            await vi.advanceTimersByTimeAsync(220)
            await flushPromises()
            expect(testOcr).toHaveBeenCalledTimes(2)

            await wrapper.find('.result-header button').trigger('click')
            await flushPromises()
            expect(testOcr).toHaveBeenCalledTimes(3)
            wrapper.unmount()
        } finally {
            vi.useRealTimers()
        }
    })
})
