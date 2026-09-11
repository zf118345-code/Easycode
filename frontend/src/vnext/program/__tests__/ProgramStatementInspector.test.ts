import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ProgramStatementInspector from '../ProgramStatementInspector.vue'
import { vnextApi } from '../../api'
import type { CallStatement, ProgramFunctionContract, ProgramStatement } from '../types'

const contract: ProgramFunctionContract = {
    function_id: 'builtin.log.output',
    display_name: '日志.输出',
    parameters: [{
        parameter_id: 'content',
        display_name: '内容',
        value_type: 'string',
        required: true,
        allowed_sources: ['fixed', 'reference', 'computed'],
    }],
    return_type: 'string',
}

function callStatement(): CallStatement {
    return {
        statement_id: 'stmt_log',
        kind: 'call',
        function_id: contract.function_id,
        display_name: contract.display_name,
        arguments: {
            content: { value_id: 'value_content', value_type: 'string', kind: 'literal', value: '旧内容' },
        },
        result_binding: { symbol_id: 'symbol_result', display_name: '日志结果', value_type: 'string', declare: true },
    }
}

describe('ProgramStatementInspector', () => {
    it('keeps the empty inspector focused on selecting an existing step', () => {
        const wrapper = mount(ProgramStatementInspector, { props: { statement: null } })

        expect(wrapper.text()).toContain('选择流程中的一步')
        expect(wrapper.text()).toContain('参数和结果会显示在这里')
        expect(wrapper.find('.inspector-empty button').exists()).toBe(false)
    })

    it('distinguishes the effective statement target from the project default target', () => {
        const wrapper = mount(ProgramStatementInspector, {
            props: {
                statement: callStatement(),
                functionContract: contract,
                platform: 'android_adb',
                targetContextLabel: '雷电模拟器',
                targetContextDetail: '覆盖默认目标“微信”',
            },
        })

        expect(wrapper.get('.target-context').text()).toContain('语句目标')
        expect(wrapper.get('.target-context').text()).toContain('雷电模拟器')
        expect(wrapper.get('.target-context').attributes('title')).toBe('ADB 控件')
        expect(wrapper.get('.target-context').text()).toContain('覆盖默认目标“微信”')
        expect(wrapper.get('.target-context').text()).not.toContain('当前目标')
    })

    it('does not repeat an inherited default target in every ordinary call', () => {
        const wrapper = mount(ProgramStatementInspector, {
            props: {
                statement: callStatement(),
                functionContract: contract,
                platform: 'windows',
                targetContextLabel: '微信',
                targetContextDetail: '继承项目默认目标',
            },
        })

        expect(wrapper.find('.target-context').exists()).toBe(false)
    })

    it('shows all Program Service-backed call editors by default', () => {
        const wrapper = mount(ProgramStatementInspector, {
            props: { statement: callStatement(), functionContract: contract },
        })

        expect(wrapper.find('.program-parameter').exists()).toBe(true)
        expect(wrapper.find('.result-section').exists()).toBe(true)
        expect(wrapper.find('.secondary-settings').exists()).toBe(true)
        expect(wrapper.text()).not.toContain('函数调用')
        expect(wrapper.find('.source-actions').exists()).toBe(false)
        expect(wrapper.get('.expression-surface').text()).toContain('旧内容')
    })

    it('offers one Program Service recovery action instead of one error card per missing field', async () => {
        const incompleteContract: ProgramFunctionContract = {
            ...contract,
            parameters: [
                ...contract.parameters,
                {
                    parameter_id: 'level', display_name: '级别', value_type: 'string', required: false,
                    allowed_sources: ['fixed'], ui: { control: 'expression', importance: 'advanced' },
                },
            ],
        }
        const wrapper = mount(ProgramStatementInspector, {
            props: {
                statement: callStatement(),
                functionContract: incompleteContract,
                supportedCommands: ['repair_missing_arguments', 'update_value'],
            },
        })

        expect(wrapper.findAll('.parameter-recovery')).toHaveLength(1)
        expect(wrapper.text()).toContain('缺少 1 个参数节点')
        expect(wrapper.text()).not.toContain('参数结构缺失')
        await wrapper.get('.parameter-recovery button').trigger('click')
        expect(wrapper.emitted('command')?.[0]?.[0]).toEqual({
            kind: 'repair_missing_arguments',
            statement_id: 'stmt_log',
        })
    })

    it('uses one composer for open scalar content and a plain select for fixed contract choices', async () => {
        const logContract: ProgramFunctionContract = {
            function_id: 'official.log.output', display_name: '日志.输出', return_type: 'void',
            parameters: [
                {
                    parameter_id: 'content', display_name: '内容', value_type: 'any', required: true,
                    allowed_sources: ['fixed', 'reference', 'computed'],
                },
                {
                    parameter_id: 'level', display_name: '级别', value_type: 'enum<log_level>', required: false,
                    allowed_sources: ['fixed'],
                    constraints: { choices: [{ label: '信息', value: 'info' }, { label: '警告', value: 'warning' }] },
                    ui: { control: 'select' },
                },
            ],
        }
        const statement: CallStatement = {
            statement_id: 'stmt_log_modes', kind: 'call', function_id: logContract.function_id,
            display_name: logContract.display_name,
            arguments: {
                content: { value_id: 'value_log_content', kind: 'literal', value_type: 'string', value: '原内容' },
                level: { value_id: 'value_log_level', kind: 'literal', value_type: 'string', value: 'info' },
            },
        }
        const wrapper = mount(ProgramStatementInspector, {
            props: { statement, functionContract: logContract },
        })

        expect(wrapper.findAll('.expression-surface')).toHaveLength(1)
        expect(wrapper.findAll('.program-parameter select')).toHaveLength(1)
        expect(wrapper.find('.source-actions').exists()).toBe(false)
        expect(wrapper.text()).not.toContain('变量计算')

        await wrapper.get('.expression-surface').trigger('click')
        expect(wrapper.find('.expression-editor').exists()).toBe(true)
        expect(wrapper.find('.expression-tools').exists()).toBe(false)
        expect(wrapper.text()).not.toContain('更多操作')
        expect(wrapper.text()).not.toContain('取消')
        expect(wrapper.text()).not.toContain('确定')
        await wrapper.get('[aria-label="内容的填写帮助"]').trigger('click')
        expect(wrapper.get('.expression-help').text()).toContain('输入 @ 先选择变量或结果')
    })

    it('copies the stable statement identity without adding visible metadata noise', async () => {
        const writeText = vi.fn().mockResolvedValue(undefined)
        vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
        const wrapper = mount(ProgramStatementInspector, {
            props: { statement: callStatement(), functionContract: contract },
        })

        await wrapper.get('[aria-label="复制语句 ID：stmt_log"]').trigger('click')
        await Promise.resolve()

        expect(writeText).toHaveBeenCalledWith('stmt_log')
        expect(wrapper.get('[aria-live="polite"]').text()).toContain('已复制语句 ID')
        expect(wrapper.text()).not.toContain('stmt_log')
        await wrapper.get('[aria-label="在 Player 中查找可发布参数"]').trigger('click')
        expect(wrapper.emitted('locatePlayer')?.[0]).toEqual(['stmt_log'])
        vi.unstubAllGlobals()
    })

    it('edits typed values and return bindings instead of showing passive metadata', async () => {
        const wrapper = mount(ProgramStatementInspector, {
            props: {
                statement: callStatement(),
                functionContract: contract,
                supportedCommands: ['update_value', 'set_result_binding'],
            },
        })

        await wrapper.get('.program-parameter .expression-surface').trigger('click')
        const valueInput = wrapper.get('.program-parameter .expression-editor')
        await valueInput.setValue('新内容')
        await valueInput.trigger('keydown.enter')
        expect(wrapper.emitted('command')?.[0]?.[0]).toEqual({
            kind: 'update_value',
            statement_id: 'stmt_log',
            parameter_id: 'content',
            value_id: 'value_content',
            next: { value_id: 'value_content', kind: 'literal', value_type: 'string', value: '新内容' },
        })

        const resultInput = wrapper.get('.result-section input')
        await resultInput.setValue('新的日志结果')
        await resultInput.trigger('keydown.enter')
        expect(wrapper.emitted('command')?.at(-1)?.[0]).toEqual({
            kind: 'set_result_binding',
            statement_id: 'stmt_log',
            target: { kind: 'new_local', display_name: '新的日志结果' },
        })
        expect(wrapper.text()).not.toContain('支持平台')
        expect(wrapper.text()).not.toContain('实现分类')
    })

    it('hides internal parameters and keeps low-frequency settings collapsed', () => {
        const layeredContract: ProgramFunctionContract = {
            ...contract,
            parameters: [
                { ...contract.parameters[0], ui: { control: 'expression', importance: 'primary' } },
                { parameter_id: 'interval', display_name: '检查间隔', value_type: 'duration', required: false, allowed_sources: ['fixed'], ui: { control: 'expression', importance: 'advanced' } },
                { parameter_id: 'category', display_name: '分类', value_type: 'string', required: false, allowed_sources: ['fixed'], ui: { control: 'expression', importance: 'internal' } },
            ],
        }
        const statement = callStatement()
        statement.arguments.interval = { value_id: 'value_interval', kind: 'literal', value_type: 'duration', value: 100 }
        statement.arguments.category = { value_id: 'value_category', kind: 'literal', value_type: 'string', value: 'script' }
        const wrapper = mount(ProgramStatementInspector, { props: { statement, functionContract: layeredContract } })

        expect(wrapper.text()).toContain('高级参数')
        expect(wrapper.text()).not.toContain('分类')
        expect(wrapper.get('.advanced-parameters').attributes('open')).toBeUndefined()
    })

    it('uses a stable form hierarchy instead of generic secondary headings', () => {
        const wrapper = mount(ProgramStatementInspector, {
            props: { statement: callStatement(), functionContract: contract },
        })

        expect(wrapper.get('#parameter-heading').text()).toBe('参数')
        expect(wrapper.get('#result-heading').text()).toBe('结果')
        expect(wrapper.get('.secondary-settings summary').text()).toBe('步骤备注')
        expect(wrapper.text()).not.toContain('其他')
        expect(wrapper.get('.program-parameter').attributes('role')).toBe('group')
        expect(wrapper.find('.program-parameter legend').exists()).toBe(false)
    })

    it('can save a result into an existing compatible local variable', async () => {
        const wrapper = mount(ProgramStatementInspector, {
            props: {
                statement: { ...callStatement(), result_binding: null },
                functionContract: contract,
                availableValues: [
                    { source: 'local', id: 'symbol_existing', display_name: '已有结果', value_type: 'string' },
                    { source: 'project', id: 'project_result', display_name: '项目结果', value_type: 'string' },
                ],
            },
        })

        const input = wrapper.get('.result-section input')
        await input.trigger('focus')
        await input.setValue('@已有')
        expect(wrapper.text()).toContain('已有结果')
        expect(wrapper.text()).not.toContain('项目结果')
        await wrapper.get('.result-binding-suggestions button').trigger('click')
        expect(wrapper.emitted('command')?.at(-1)?.[0]).toEqual({
            kind: 'set_result_binding', statement_id: 'stmt_log',
            target: { kind: 'existing_local', symbol_id: 'symbol_existing', display_name: '已有结果', value_type: 'string' },
        })
    })

    it('creates an adjacent typed condition for bool or optional call results', async () => {
        const boolContract: ProgramFunctionContract = { ...contract, return_type: 'bool' }
        const wrapper = mount(ProgramStatementInspector, {
            props: {
                statement: { ...callStatement(), result_binding: undefined },
                functionContract: boolContract,
                supportedCommands: ['set_result_binding', 'insert_if_from_call_result'],
            },
        })

        const resultRow = wrapper.get('.result-control-row')
        expect(resultRow.find('.result-binding-input').exists()).toBe(true)
        expect(resultRow.find('.result-condition-action').exists()).toBe(true)
        expect(wrapper.get('.result-condition-action button').attributes('title')).toBe('在下一行添加“如果结果成立”')
        expect(wrapper.get('.result-condition-action button').attributes('aria-label')).toBe('在下一行添加“如果结果成立”')
        expect(wrapper.text()).not.toContain('在下一行添加“如果结果成立”')
        await wrapper.get('.result-condition-action button').trigger('click')
        expect(wrapper.emitted('command')?.[0]?.[0]).toEqual({
            kind: 'insert_if_from_call_result',
            statement_id: 'stmt_log',
        })

        await wrapper.setProps({ functionContract: { ...contract, return_type: 'optional<string>' } })
        expect(wrapper.get('.result-condition-action button').attributes('title')).toBe('在下一行添加“如果有结果”')
        await wrapper.setProps({ functionContract: contract })
        expect(wrapper.find('.result-condition-action').exists()).toBe(false)
    })

    it('routes capture actions with stable statement, parameter and value identities', async () => {
        const pointContract: ProgramFunctionContract = {
            function_id: 'builtin.input.click',
            display_name: '输入.点击',
            return_type: 'void',
            parameters: [{
                parameter_id: 'position',
                display_name: '位置',
                value_type: 'point',
                required: true,
                allowed_sources: ['fixed', 'reference', 'computed'],
                ui: { control: 'coordinate', actions: [{ id: 'pick-point', capture_kind: 'point', platforms: ['windows'] }] },
            }],
        }
        const statement: CallStatement = {
            statement_id: 'stmt_click',
            kind: 'call',
            function_id: pointContract.function_id,
            display_name: pointContract.display_name,
            arguments: {
                position: { value_id: 'value_position', value_type: 'point', kind: 'literal', value: [10, 20] },
            },
        }
        const wrapper = mount(ProgramStatementInspector, {
            props: { statement, functionContract: pointContract, platform: 'windows' },
        })

        expect(wrapper.get('.expression-surface').text()).toContain('坐标(10, 20)')
        expect(wrapper.find('.source-actions').exists()).toBe(false)
        expect(wrapper.text()).not.toContain('计算')
        await wrapper.get('button[aria-label="取点"]').trigger('click')
        expect(wrapper.emitted('capture')?.[0]?.[0]).toEqual({
            statement_id: 'stmt_click',
            parameter_id: 'position',
            value_id: 'value_position',
            action: { id: 'pick-point', capture_kind: 'point', platforms: ['windows'] },
        })
    })

    it('keeps a captured control as a compact actionable Control instead of exposing selector internals', async () => {
        const selectorContract: ProgramFunctionContract = {
            function_id: 'official.control.find',
            display_name: '控件.查找',
            return_type: 'control_ref',
            parameters: [{
                parameter_id: 'selector',
                display_name: '控件选择器',
                value_type: 'control_selector',
                required: true,
                allowed_sources: ['fixed'],
                ui: { control: 'control-selector', actions: [{ id: 'capture-control', capture_kind: 'control', platforms: ['windows', 'android_adb'] }] },
            }],
        }
        const statement: CallStatement = {
            statement_id: 'stmt_control',
            kind: 'call',
            function_id: selectorContract.function_id,
            display_name: selectorContract.display_name,
            arguments: {
                selector: {
                    value_id: 'value_selector', value_type: 'control_selector', kind: 'record', record_type: 'control_selector',
                    fields: {
                        'control_selector.field.name': { value_id: 'value_name', value_type: 'string', kind: 'literal', value: '确认按钮' },
                        'control_selector.field.automation_id': { value_id: 'value_id', value_type: 'string', kind: 'literal', value: 'confirm' },
                    },
                },
            },
        }
        const wrapper = mount(ProgramStatementInspector, {
            props: { statement, functionContract: selectorContract, platform: 'windows' },
        })

        expect(wrapper.text()).toContain('确认按钮')
        expect(wrapper.text()).toContain('confirm')
        expect(wrapper.text()).not.toContain('编辑内容')
        expect(wrapper.text()).not.toContain('control_selector.field')
        await wrapper.get('button[aria-label="捕获控件"]').trigger('click')
        expect(wrapper.emitted('capture')?.[0]?.[0]).toMatchObject({
            statement_id: 'stmt_control', parameter_id: 'selector', value_id: 'value_selector',
        })
    })

    it('uses direct image selection and previews the current frame with runtime parameters', async () => {
        const imageContract: ProgramFunctionContract = {
            function_id: 'official.image.find', display_name: '查找图像', return_type: 'optional<image_match>',
            parameters: [
                {
                    parameter_id: 'official.image.find.parameter.image', display_name: '图片', value_type: 'asset_ref<image>', required: true,
                    allowed_sources: ['fixed'], ui: { control: 'resource' },
                },
                {
                    parameter_id: 'official.image.find.parameter.similarity', display_name: '相似度', value_type: 'percentage', required: false,
                    allowed_sources: ['fixed'], ui: { control: 'slider-number' },
                },
                {
                    parameter_id: 'official.image.find.parameter.region', display_name: '区域', value_type: 'optional<rect>', required: false,
                    allowed_sources: ['fixed'], ui: { control: 'region' },
                },
            ],
        }
        const statement: CallStatement = {
            statement_id: 'stmt_find', kind: 'call', function_id: imageContract.function_id,
            display_name: imageContract.display_name,
            arguments: {
                'official.image.find.parameter.image': { value_id: 'value_image', kind: 'asset_ref', value_type: 'asset_ref<image>', asset_id: 'asset.button', asset_kind: 'image' },
                'official.image.find.parameter.similarity': { value_id: 'value_similarity', kind: 'literal', value_type: 'percentage', value: 0.85 },
                'official.image.find.parameter.region': { value_id: 'value_region', kind: 'literal', value_type: 'optional<rect>', value: [1, 2, 30, 40] },
            },
        }
        const preview = vi.spyOn(vnextApi, 'previewVision').mockResolvedValue({
            kind: 'image', preview_data_url: 'data:image/png;base64,AA==', matched: true,
            similarity: 0.93, threshold: 0.85, text: '', line_count: 0,
            target_id: 'target.windows', captured_at: '2026-09-06T12:00:00Z',
            requested_region: [1, 2, 30, 40], actual_region: [1, 2, 30, 40],
            region_clipped: false, region_empty: false,
        })
        const wrapper = mount(ProgramStatementInspector, {
            props: {
                statement, functionContract: imageContract,
                workspace: {
                    workspace_id: 'workspace', generation: 2, project_id: 'project', project_name: 'Project',
                    project_path: 'D:/project', read_only: false,
                },
                targetId: 'target.windows', platform: 'windows',
                assets: [{
                    asset_id: 'asset.button', display_name: '确认按钮', category: 'image', folder: '', path: 'button.png',
                    extension: '.png', mime_type: 'image/png', size_bytes: 100, width: 30, height: 40,
                    sha256: 'abc', source: 'capture', created_at: '', updated_at: '', aliases: [], capture: null,
                }],
            },
        })

        expect(wrapper.find('.program-parameter[data-value-id="value_image"] .expression-surface').exists()).toBe(false)
        expect((wrapper.get('.program-parameter[data-value-id="value_image"] .value-resource select').element as HTMLSelectElement).value).toBe('asset.button')
        expect(wrapper.get('.program-parameter[data-value-id="value_image"] .value-resource select').text()).toContain('确认按钮')
        expect(wrapper.get('.inspector-header .vnext-pane-header__title').text()).toBe('查找图像')
        expect(wrapper.get('.vision-preview-action').text()).toBe('测试')
        expect(wrapper.find('.vision-preview-section').exists()).toBe(false)
        await wrapper.get('.vision-preview-action').trigger('click')
        await Promise.resolve()
        await Promise.resolve()

        expect(preview).toHaveBeenCalledWith(expect.objectContaining({ workspace_id: 'workspace' }), expect.objectContaining({
            target_id: 'target.windows', function_id: 'official.image.find', image_asset_id: 'asset.button',
            similarity: 0.85, region: [1, 2, 30, 40],
        }))
        expect(wrapper.get('.vision-preview-result').text()).toContain('已匹配 · 相似度 93%')
        expect(wrapper.get('.vision-preview-result').text()).toContain('实际区域 (1, 2) 30×40')
        expect(wrapper.get('.vision-preview-result').text()).toContain('当前阈值 85%')
        expect(wrapper.get('.vision-preview-result img').attributes('src')).toBe('data:image/png;base64,AA==')

        preview.mockResolvedValueOnce({
            kind: 'image', preview_data_url: 'data:image/png;base64,BB==', matched: false,
            similarity: 0.842, threshold: 0.85, text: '', line_count: 0,
            target_id: 'target.windows', captured_at: '2026-09-06T12:00:01Z',
            requested_region: [1, 2, 30, 40], actual_region: [1, 2, 30, 40],
            region_clipped: false, region_empty: false,
        })
        await wrapper.get('.vision-preview-action').trigger('click')
        await flushPromises()
        expect(wrapper.get('.vision-preview-result').text()).toContain('未匹配 · 最高相似度 84%')
        expect(wrapper.get('.vision-preview-result').text()).toContain('当前阈值 85%')

        preview.mockResolvedValueOnce({
            kind: 'image', preview_data_url: '', matched: false,
            similarity: null, threshold: 0.85, text: '', line_count: 0,
            target_id: 'target.windows', captured_at: '2026-09-06T12:00:02Z',
            requested_region: [100, 100, 30, 40], actual_region: [80, 40, 0, 0],
            region_clipped: true, region_empty: true,
        })
        await wrapper.get('.vision-preview-action').trigger('click')
        await flushPromises()
        expect(wrapper.find('.vision-preview-result img').exists()).toBe(false)
        expect(wrapper.get('.vision-preview-empty').text()).toContain('无有效区域')
        expect(wrapper.get('.vision-preview-result').text()).toContain('未匹配 · 区域无有效像素')
        expect(wrapper.get('.vision-preview-result').text()).toContain('已按当前画面裁剪')
        preview.mockRestore()
    })

    it('requires a server-backed author review for dangerous calls', async () => {
        const dangerousContract: ProgramFunctionContract = {
            ...contract,
            function_id: 'official.directory.delete_tree',
            display_name: '目录.递归删除',
            dangerous: true,
        }
        const statement: CallStatement = {
            ...callStatement(),
            statement_id: 'stmt_delete_tree',
            function_id: dangerousContract.function_id,
            display_name: dangerousContract.display_name,
            author_review_fingerprint: null,
        }
        const wrapper = mount(ProgramStatementInspector, {
            props: {
                statement,
                functionContract: dangerousContract,
                diagnostics: [{
                    code: 'PGM-DANGER-001',
                    severity: 'error',
                    message: '危险调用尚未审核',
                    statement_id: statement.statement_id,
                }],
                supportedCommands: ['review_dangerous_call'],
            },
        })

        expect(wrapper.get('.danger-review').text()).toContain('递归删除不可回滚')
        await wrapper.get('.danger-review button').trigger('click')
        expect(wrapper.emitted('command')?.[0]?.[0]).toEqual({
            kind: 'review_dangerous_call',
            statement_id: statement.statement_id,
        })
    })

    it('exposes only server-backed structure fields and keeps missing contracts editable-safe', async () => {
        const statement: ProgramStatement = {
            statement_id: 'stmt_try',
            kind: 'try',
            body: [],
            retry_policy: null,
            catches: [],
            finally_body: [],
        }
        const wrapper = mount(ProgramStatementInspector, {
            props: { statement },
        })

        expect(wrapper.get('.inspector-header .vnext-pane-header__title').text()).toBe('尝试')
        expect(wrapper.find('.statement-kind').exists()).toBe(false)
        expect(wrapper.get('.structure-inspector').text()).toContain('失败后重试')
        expect(wrapper.get('.structure-inspector').text()).not.toContain('失败后重新尝试')
        expect(wrapper.get('.structure-inspector').text()).not.toContain('异常区域')
        expect(wrapper.get('.check-field').attributes('title')).toContain('只处理运行错误')
        expect(wrapper.get('.structure-inspector').text()).not.toContain('图片未找到等正常结果')
        await wrapper.get('.check-field input').setValue(true)
        const command = wrapper.emitted('command')?.[0]?.[0] as { kind: string; retry_policy: unknown }
        expect(command.kind).toBe('update_try_retry_policy')
        expect(command.retry_policy).toBeTruthy()

        await wrapper.setProps({ statement: callStatement(), functionContract: null })
        expect(wrapper.get('[role="alert"]').text()).toContain('函数契约不可用')
        expect(wrapper.find('.program-parameter').exists()).toBe(false)
    })
})
