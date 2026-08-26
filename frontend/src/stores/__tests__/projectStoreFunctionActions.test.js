import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useProjectStore } from '@/stores/projectStore'
import { blueprintApi } from '@/api/blueprintApi'
import { createFunctionDefinition, createMainGraph, createPageMap } from '@/utils/flowModel'

vi.mock('@/api/blueprintApi', () => ({
    blueprintApi: {
        saveFunction: vi.fn(),
        deleteFunction: vi.fn(),
        createFunction: vi.fn(),
        duplicateFunction: vi.fn(),
        getBlueprint: vi.fn(),
        getWorkflow: vi.fn(),
        getTopology: vi.fn(),
    }
}))

describe('projectStore 函数操作', () => {
    let store
    let fn

    beforeEach(() => {
        vi.clearAllMocks()
        setActivePinia(createPinia())
        store = useProjectStore()
        fn = createFunctionDefinition('登录')
        store.currentProjectPath = 'D:/test/proj'
        store.blueprint = {
            schema_version: 3,
            main_graph: createMainGraph(),
            functions: [fn],
            function_folders: [],
            page_map: createPageMap(),
            variables: {}, ui_state: {}, settings: {},
        }
    })

    it('保存函数契约与独立画布', async () => {
        blueprintApi.saveFunction.mockResolvedValue({ status: 'success' })
        fn.description = '执行登录并返回结果'
        await store.saveFunctionData(fn)
        expect(blueprintApi.saveFunction).toHaveBeenCalledWith(fn.function_id, 'D:/test/proj', fn)
    })

    it('无引用时删除函数并回到主流程', async () => {
        blueprintApi.deleteFunction.mockResolvedValue({ status: 'success' })
        store.currentTaskId = fn.function_id
        await store.deleteFunction(fn.function_id)
        expect(blueprintApi.deleteFunction).toHaveBeenCalledWith(fn.function_id, 'D:/test/proj')
        expect(store.blueprint.functions).toEqual([])
        expect(store.currentTaskId).toBe('main')
    })

    it('存在调用节点时拒绝删除被引用函数', async () => {
        store.blueprint.main_graph.nodes.push({ node_id: 'call_1', node_type: 'call_function', params: { function_id: fn.function_id } })
        await expect(store.deleteFunction(fn.function_id)).rejects.toThrow('调用函数节点')
        expect(blueprintApi.deleteFunction).not.toHaveBeenCalled()
    })
})
