import { describe, expect, it } from 'vitest'
import { buildFunctionCatalog, searchFunctionCatalog } from '../functionCatalogSearch'
import type { AvailableFunctionContractDto } from '../serverTypes'

function official(
    functionId: string,
    namespace: string,
    name: string,
    summary = name,
    returnType = 'unit',
): AvailableFunctionContractDto {
    return {
        function_id: functionId, namespace, name, summary,
        qualified_name: `${namespace}.${name}`, layer: 'atomic', parameters: [], return_type: returnType,
        opcode: functionId, host_requirements: ['windows'], target_kinds: [], target_capabilities: [],
        permissions: [], side_effects: [], errors: [], normal_empty: false, network_level: 'none',
        dangerous: false, implementation_state: 'available', standard_definition_id: '',
        contract_version: '1.0.0', schema_version: 1, contract_fingerprint: functionId,
    }
}

describe('functionCatalogSearch', () => {
    it('searches structures and callable functions through one semantic index', () => {
        const catalog = buildFunctionCatalog({
            officialFunctions: [
                official('official.control.click', '控件', '点击', '点击{control}'),
                official('official.wait.duration', '等待', '持续'),
            ],
        })

        expect(searchFunctionCatalog(catalog, '控件').map((item) => item.key)).toContain('official:official.control.click')
        expect(searchFunctionCatalog(catalog, '判断')[0]?.key).toBe('structure:if')
        expect(searchFunctionCatalog(catalog, '结束循环')[0]?.key).toBe('structure:break')
    })

    it('ranks exact semantic names first, remembers recent choices when empty, and blocks self calls', () => {
        const catalog = buildFunctionCatalog({
            activeFunctionId: 'func-main',
            projectFunctions: [{
                document_id: 'doc-main', function_id: 'func-main', display_name: '主程序', statement_count: 2,
                revision: 'r1', parameters: [], return_type: 'null', contract_version: '1.0.0', contract_fingerprint: 'fp',
                insertable: true,
            }],
            officialFunctions: [official('official.log.output', '日志', '输出', '输出内容')],
        })

        expect(searchFunctionCatalog(catalog, '输出内容')[0]?.key).toBe('official:official.log.output')
        expect(searchFunctionCatalog(catalog, '', { recentKeys: ['official:official.log.output'] })[0]?.key)
            .toBe('official:official.log.output')
        expect(catalog.find((item) => item.key === 'project:func-main')?.disabledReason).toContain('自身')
    })

    it('offers atomic call-and-condition shortcuts only for bool and optional results', () => {
        const catalog = buildFunctionCatalog({
            officialFunctions: [
                official('official.image.find', '图像', '查找', '查找{image}', 'optional<image_match>'),
                official('official.file.exists', '文件', '存在', '文件{path}存在', 'bool'),
                official('official.wait.duration', '等待', '持续'),
            ],
        })

        expect(catalog.find((item) => item.key === 'official:official.image.find:call-and-if')?.selection)
            .toEqual({ source: 'official', function_id: 'official.image.find', intent: 'call_and_if' })
        expect(searchFunctionCatalog(catalog, '调用并判断')[0]?.key)
            .toBe('official:official.image.find:call-and-if')
        expect(catalog.some((item) => item.key === 'official:official.file.exists:call-and-if')).toBe(true)
        expect(catalog.some((item) => item.key === 'official:official.wait.duration:call-and-if')).toBe(false)
        expect(searchFunctionCatalog(catalog, '重复直到')[0]?.selection)
            .toEqual({ source: 'official', function_id: 'official.image.find', intent: 'execute_until' })
        expect(searchFunctionCatalog(catalog, '向左拖动直到图片出现')[0]?.selection)
            .toEqual({ source: 'official', function_id: 'official.image.find', intent: 'execute_until' })
    })

    it('lets keyboard authors find project functions by their parameter intent', () => {
        const catalog = buildFunctionCatalog({
            projectFunctions: [{
                document_id: 'doc-battle', function_id: 'function-battle', display_name: '战斗-刷图', statement_count: 20,
                revision: 'r1', return_type: 'null', contract_version: '1.0.0', contract_fingerprint: 'fp', insertable: true,
                parameters: [{
                    parameter_id: 'parameter-count', symbol_id: 'symbol-count', display_name: '最大战斗次数',
                    value_type: 'int64', required: true, default_value: null,
                }],
            }],
        })

        expect(searchFunctionCatalog(catalog, '最大战斗次数')[0]?.key).toBe('project:function-battle')
        expect(searchFunctionCatalog(catalog, '调用项目函数')[0]?.key).toBe('project:function-battle')
    })
})
