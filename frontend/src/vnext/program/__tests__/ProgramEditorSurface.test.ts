import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ProgramEditorSurface from '../ProgramEditorSurface.vue'
import VNextPaneResizer from '../../components/VNextPaneResizer.vue'
import type { ProgramDocument, ProgramFunctionContract } from '../types'

const contract: ProgramFunctionContract = {
    function_id: 'builtin.wait.duration',
    display_name: '等待.持续',
    return_type: 'void',
    parameters: [{
        parameter_id: 'duration',
        display_name: '时长',
        value_type: 'duration',
        required: true,
        allowed_sources: ['fixed'],
        ui: { control: 'duration' },
    }],
}

function document(): ProgramDocument {
    return {
        schema_version: 1,
        document_id: 'doc_main',
        revision: 'revision-7',
        function: {
            function_id: 'function_main',
            display_name: '主程序',
            parameters: [],
            return_type: 'null',
            statements: [{
                statement_id: 'stmt_wait',
                kind: 'call',
                function_id: contract.function_id,
                display_name: contract.display_name,
                arguments: {
                    duration: {
                        value_id: 'value_duration',
                        value_type: 'duration',
                        kind: 'literal',
                        value: { milliseconds: 1000 },
                    },
                },
            }],
        },
    }
}

describe('ProgramEditorSurface', () => {
    afterEach(() => { vi.unstubAllGlobals() })

    it('wraps every edit in the document identity and optimistic revision', async () => {
        const wrapper = mount(ProgramEditorSurface, {
            props: {
                document: document(),
                selectedStatementIds: ['stmt_wait'],
                functionContracts: { [contract.function_id]: contract },
            },
        })

        await wrapper.get('.program-parameter .expression-surface').trigger('click')
        const durationInput = wrapper.get('.program-parameter .expression-editor')
        await durationInput.setValue('2 秒')
        await durationInput.trigger('keydown.enter')

        expect(wrapper.emitted('command')?.[0]?.[0]).toEqual({
            document_id: 'doc_main',
            base_revision: 'revision-7',
            command: {
                kind: 'update_value',
                statement_id: 'stmt_wait',
                parameter_id: 'duration',
                value_id: 'value_duration',
                next: { value_id: 'value_duration', kind: 'literal', value_type: 'duration', value: 2000 },
            },
        })

        await wrapper.get('[data-statement-id="stmt_wait"]').trigger('keydown', { key: 'd', ctrlKey: true })
        expect(wrapper.emitted('command')?.at(-1)?.[0]).toEqual({
            document_id: 'doc_main',
            base_revision: 'revision-7',
            command: { kind: 'duplicate_statements', statement_ids: ['stmt_wait'] },
        })
    })

    it('uses an explicit inspector drawer on compact workspaces', async () => {
        const removeEventListener = vi.fn()
        vi.stubGlobal('matchMedia', vi.fn(() => ({
            matches: true,
            addEventListener: vi.fn(),
            removeEventListener,
        })))

        const wrapper = mount(ProgramEditorSurface, {
            attachTo: globalThis.document.body,
            props: {
                document: document(),
                selectedStatementIds: ['stmt_wait'],
                functionContracts: { [contract.function_id]: contract },
            },
        })
        await wrapper.vm.$nextTick()

        expect(wrapper.find('.statement-inspector').exists()).toBe(false)
        expect(wrapper.get('[aria-label="打开语句检查器"]')).toBeTruthy()

        await wrapper.get('[aria-label="打开语句检查器"]').trigger('click')
        await wrapper.vm.$nextTick()
        expect(wrapper.get('.statement-inspector').classes()).toContain('is-drawer')
        expect(wrapper.get('.inspector-drawer-scrim')).toBeTruthy()
        expect(globalThis.document.activeElement).toBe(wrapper.get('[aria-label="关闭语句检查器"]').element)

        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
        await wrapper.vm.$nextTick()
        expect(wrapper.find('.statement-inspector').exists()).toBe(false)
        expect(globalThis.document.activeElement).toBe(wrapper.get('[aria-label="打开语句检查器"]').element)

        wrapper.unmount()
        expect(removeEventListener).toHaveBeenCalledWith('change', expect.any(Function))
    })

    it('does not duplicate the function-library action inside an unselected inspector', () => {
        vi.stubGlobal('matchMedia', vi.fn(() => ({
            matches: false,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
        })))
        const wrapper = mount(ProgramEditorSurface, {
            props: { document: document(), selectedStatementIds: [] },
        })

        expect(wrapper.get('.inspector-empty').text()).toContain('选择流程中的一步')
        expect(wrapper.find('.inspector-empty button').exists()).toBe(false)
        expect(wrapper.emitted('requestFunctionLibrary')).toBeUndefined()
    })

    it('uses the shared parameter control for atomic same-function batch editing', async () => {
        const batchDocument = document()
        batchDocument.function.statements.push({
            statement_id: 'stmt_wait_2', kind: 'call', function_id: contract.function_id,
            display_name: contract.display_name,
            arguments: {
                duration: {
                    value_id: 'value_duration_2', value_type: 'duration', kind: 'literal',
                    value: { milliseconds: 2000 },
                },
            },
        })
        const wrapper = mount(ProgramEditorSurface, {
            props: {
                document: batchDocument,
                selectedStatementIds: ['stmt_wait', 'stmt_wait_2'],
                functionContracts: { [contract.function_id]: contract },
            },
        })

        expect(wrapper.text()).toContain('批量编辑 · 等待.持续')
        expect(wrapper.text()).toContain('2 条语句')
        await wrapper.get('.program-parameter .expression-surface').trigger('click')
        const input = wrapper.get('.program-parameter .expression-editor')
        expect(input.attributes('placeholder')).toContain('多个值')
        await input.setValue('3 秒')
        await input.trigger('keydown.enter')

        expect(wrapper.emitted('command')?.at(-1)?.[0]).toEqual({
            document_id: 'doc_main', base_revision: 'revision-7',
            command: {
                kind: 'batch_update_values',
                statement_ids: ['stmt_wait', 'stmt_wait_2'],
                parameter_id: 'duration',
                next: { value_id: 'value_duration', kind: 'literal', value_type: 'duration', value: 3000 },
            },
        })
    })

    it('opens one focused editor for a shared complex parameter across the batch', async () => {
        const mapContract: ProgramFunctionContract = {
            function_id: 'extension.map.consume',
            display_name: '字典.处理',
            return_type: 'void',
            parameters: [{
                parameter_id: 'options', display_name: '配置', value_type: 'map<string,string>',
                required: true, allowed_sources: ['fixed'], ui: { control: 'expression', editor_strategy: 'focused' },
            }],
        }
        const batchDocument = document()
        batchDocument.function.statements = ['first', 'second'].map((suffix, index) => ({
            statement_id: `stmt_${suffix}`,
            kind: 'call' as const,
            function_id: mapContract.function_id,
            display_name: mapContract.display_name,
            arguments: {
                options: {
                    value_id: `value_options_${suffix}`,
                    kind: 'map' as const,
                    value_type: 'map<string,string>',
                    key_type: 'string',
                    entry_value_type: 'string',
                    duplicate_policy: 'error' as const,
                    entries: [{
                        key: { value_id: `value_key_${suffix}`, kind: 'literal' as const, value_type: 'string', value: '重试' },
                        value: { value_id: `value_item_${suffix}`, kind: 'literal' as const, value_type: 'string', value: String(index + 1) },
                    }],
                },
            },
        }))
        const wrapper = mount(ProgramEditorSurface, {
            props: {
                document: batchDocument,
                selectedStatementIds: ['stmt_first', 'stmt_second'],
                functionContracts: { [mapContract.function_id]: mapContract },
            },
        })

        await wrapper.get('[aria-label="编辑配置"]').trigger('click')
        expect(wrapper.emitted('openValueEditor')?.at(-1)?.[0]).toEqual({
            document_id: 'doc_main',
            base_revision: 'revision-7',
            request: {
                statement_id: 'stmt_first',
                parameter_id: 'options',
                value_id: 'value_options_first',
                batch_statement_ids: ['stmt_first', 'stmt_second'],
            },
        })
    })

    it('uses reversed resizing for the inspector anchored on the right', () => {
        vi.stubGlobal('matchMedia', vi.fn(() => ({
            matches: false,
            addEventListener: vi.fn(),
            removeEventListener: vi.fn(),
        })))
        const wrapper = mount(ProgramEditorSurface, {
            props: {
                document: document(),
                selectedStatementIds: ['stmt_wait'],
                functionContracts: { [contract.function_id]: contract },
            },
        })

        expect(wrapper.getComponent(VNextPaneResizer).props('reverse')).toBe(true)
    })
})
