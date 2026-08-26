import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'
import CanvasLogPanel from '../canvas/CanvasLogPanel.vue'
import { useExecutionStore } from '@/stores'

vi.mock('element-plus', () => ({
    ElMessage: { success: vi.fn(), error: vi.fn() }
}))

const ButtonStub = {
    inheritAttrs: false,
    template: '<button v-bind="$attrs" @click="$emit(\'click\')"><slot /></button>'
}

function mountPanel() {
    return mount(CanvasLogPanel, {
        global: {
            stubs: {
                'el-switch': true,
                'el-tooltip': { template: '<div><slot /></div>' },
                'el-button': ButtonStub
            }
        }
    })
}

describe('CanvasLogPanel 分类、跟随与日志操作', () => {
    beforeEach(() => {
        setActivePinia(createPinia())
        vi.clearAllMocks()
        global.ResizeObserver = class {
            observe() {}
            disconnect() {}
        }
    })

    it('复制按钮会把当前全部日志按时间和消息写入剪贴板', async () => {
        const writeText = vi.fn().mockResolvedValue(undefined)
        Object.defineProperty(navigator, 'clipboard', {
            configurable: true,
            value: { writeText }
        })
        const execution = useExecutionStore()
        execution.executionLogs = [
            { time: '18:24:26', message: '任务开始' },
            { time: '18:24:27', message: '变量已更新' }
        ]

        const wrapper = mountPanel()
        await wrapper.get('button[aria-label="复制全部日志"]').trigger('click')
        await flushPromises()

        expect(writeText).toHaveBeenCalledWith('[18:24:26] 任务开始\n[18:24:27] 变量已更新')
        expect(ElMessage.success).toHaveBeenCalledWith('已复制 2 条日志')
    })

    it('按后端分类筛选显示，问题视图跨分类聚合警告和错误', async () => {
        const execution = useExecutionStore()
        execution.executionLogs = [
            { time: '10:00:00', category: 'vision', level: 'info', message: '[OCR] 识别文字="开始"' },
            { time: '10:00:01', category: 'navigation', level: 'warning', message: '[智能跳转] 路径偏离' },
            { time: '10:00:02', category: 'operation', level: 'error', message: '点击失败' }
        ]
        const wrapper = mountPanel()

        const filter = label => wrapper.findAll('.log-filter-button').find(button => button.text().startsWith(label))
        expect(filter('全部').text()).toContain('3')
        expect(filter('识别').text()).toContain('1')
        expect(filter('问题').text()).toContain('2')

        await filter('识别').trigger('click')
        expect(wrapper.text()).toContain('识别文字="开始"')
        expect(wrapper.text()).not.toContain('路径偏离')

        await filter('问题').trigger('click')
        expect(wrapper.text()).toContain('路径偏离')
        expect(wrapper.text()).toContain('点击失败')
        expect(wrapper.text()).not.toContain('识别文字="开始"')
    })

    it('清空使用图标按钮并恢复到全部分类', async () => {
        const execution = useExecutionStore()
        execution.executionLogs = [{ time: '10:00:00', category: 'vision', message: '[OCR] 文本' }]
        const wrapper = mountPanel()
        const vision = wrapper.findAll('.log-filter-button').find(button => button.text().startsWith('识别'))
        await vision.trigger('click')
        await wrapper.get('button[aria-label="清空全部日志"]').trigger('click')

        expect(execution.executionLogs).toEqual([])
        expect(wrapper.get('.log-filter-button[aria-pressed="true"]').text()).toContain('全部')
        expect(wrapper.text()).toContain('运行后将在这里显示日志')
    })
})
