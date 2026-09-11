import { describe, expect, it } from 'vitest'
import {
    EASYCODE_UI_SYSTEM_VERSION,
    validateWorkspaceUiContract,
    type WorkspaceUiContractV1,
} from '../uiSystem'

function contract(overrides: Partial<WorkspaceUiContractV1> = {}): WorkspaceUiContractV1 {
    return {
        ui_system_version: EASYCODE_UI_SYSTEM_VERSION,
        workspace_id: 'com.easycode.harness.showcase.workspace',
        display_name: '扩展展示',
        topology: 'navigator-content-inspector',
        primary_object: '展示项目',
        page_actions: [{ command_id: 'showcase.create', label: '新建展示项目', level: 'primary' }],
        states: ['loading', 'error', 'empty', 'filtered-empty', 'selection', 'readonly'],
        has_inspector: true,
        narrow_behavior: 'mutually-exclusive-drawers',
        keyboard_entry: 'Ctrl+Shift+P → 打开扩展展示',
        permission_summary: '只读取当前扩展命名空间的数据',
        danger_commands: [],
        ...overrides,
    }
}

describe('Workspace UI contract', () => {
    it('accepts a complete host-rendered extension workspace contract', () => {
        expect(validateWorkspaceUiContract(contract())).toEqual([])
    })

    it('rejects competing primary actions and missing state ownership', () => {
        const issues = validateWorkspaceUiContract(contract({
            page_actions: [
                { command_id: 'one', label: '新建', level: 'primary' },
                { command_id: 'two', label: '导入', level: 'primary' },
            ],
            states: ['loading'],
        }))
        expect(issues.map(issue => issue.message)).toEqual(expect.arrayContaining([
            '同一视图只能有一个主操作',
            '缺少 error 状态',
            '缺少 empty 状态',
            '缺少 selection 状态',
        ]))
    })

    it('requires drawer behavior whenever an inspector exists', () => {
        expect(validateWorkspaceUiContract(contract({ narrow_behavior: 'single-column' })))
            .toContainEqual({ field: 'narrow_behavior', message: '带检查器的窄屏工作区必须使用互斥抽屉' })
    })
})
