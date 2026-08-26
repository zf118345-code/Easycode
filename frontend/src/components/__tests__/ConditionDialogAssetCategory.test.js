import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import ConditionDialog from '@/components/conditions/ConditionDialog.vue'
import ParamRenderer from '@/components/ParamRenderer.vue'

describe('ConditionDialog 资源目录上下文', () => {
    it('页面特征内所有图片入口默认 page，但不限制共享文件管理器切换目录', () => {
        const wrapper = shallowMount(ConditionDialog, {
            props: { visible: true, schemaSet: 'page-feature' },
            global: {
                plugins: [createPinia()],
                stubs: {
                    'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
                    'el-select': { template: '<div><slot /></div>' },
                    'el-option': true,
                    'el-slider': true,
                    'el-button': true,
                },
            },
        })

        const fields = wrapper.findAllComponents(ParamRenderer)
        expect(fields.length).toBeGreaterThan(0)
        expect(fields.every(field => field.props('assetCategory') === 'page')).toBe(true)
        wrapper.unmount()
    })
})
