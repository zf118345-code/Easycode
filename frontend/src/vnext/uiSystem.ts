export const EASYCODE_UI_SYSTEM_VERSION = 1 as const

export type WorkspaceTopology =
    | 'navigator-content-inspector'
    | 'navigator-detail'
    | 'single-task'
    | 'player-runtime'

export type WorkspaceStateKind =
    | 'loading'
    | 'error'
    | 'empty'
    | 'filtered-empty'
    | 'selection'
    | 'readonly'
    | 'offline'

export type WorkspaceActionLevel = 'primary' | 'secondary' | 'danger'

export interface WorkspaceUiActionContract {
    command_id: string
    label: string
    level: WorkspaceActionLevel
}

/**
 * Public appearance contract for first-party workspaces and declarative
 * extension projections. It describes placement and state ownership; the host
 * still renders every control and never executes extension HTML/CSS/JS.
 */
export interface WorkspaceUiContractV1 {
    ui_system_version: typeof EASYCODE_UI_SYSTEM_VERSION
    workspace_id: string
    display_name: string
    topology: WorkspaceTopology
    primary_object: string
    page_actions: WorkspaceUiActionContract[]
    states: WorkspaceStateKind[]
    has_inspector: boolean
    narrow_behavior: 'single-column' | 'mutually-exclusive-drawers'
    keyboard_entry: string
    permission_summary: string
    danger_commands: string[]
}

export interface WorkspaceUiContractIssue {
    field: keyof WorkspaceUiContractV1 | 'page_actions'
    message: string
}

const requiredStates = new Set<WorkspaceStateKind>(['loading', 'error', 'empty', 'selection'])

export function validateWorkspaceUiContract(contract: WorkspaceUiContractV1): WorkspaceUiContractIssue[] {
    const issues: WorkspaceUiContractIssue[] = []
    if (contract.ui_system_version !== EASYCODE_UI_SYSTEM_VERSION) {
        issues.push({ field: 'ui_system_version', message: '界面系统版本不受支持' })
    }
    if (!contract.workspace_id.trim()) issues.push({ field: 'workspace_id', message: '缺少稳定工作区 ID' })
    if (!contract.display_name.trim()) issues.push({ field: 'display_name', message: '缺少面向用户的名称' })
    if (!contract.primary_object.trim()) issues.push({ field: 'primary_object', message: '缺少主对象定义' })
    if (contract.page_actions.filter(action => action.level === 'primary').length > 1) {
        issues.push({ field: 'page_actions', message: '同一视图只能有一个主操作' })
    }
    const actionIds = contract.page_actions.map(action => action.command_id)
    if (new Set(actionIds).size !== actionIds.length || actionIds.some(id => !id.trim())) {
        issues.push({ field: 'page_actions', message: '操作必须使用非空且唯一的稳定命令 ID' })
    }
    for (const state of requiredStates) {
        if (!contract.states.includes(state)) issues.push({ field: 'states', message: `缺少 ${state} 状态` })
    }
    if (contract.topology === 'navigator-content-inspector' && !contract.has_inspector) {
        issues.push({ field: 'has_inspector', message: '三栏拓扑必须声明检查器' })
    }
    if (contract.has_inspector && contract.narrow_behavior !== 'mutually-exclusive-drawers') {
        issues.push({ field: 'narrow_behavior', message: '带检查器的窄屏工作区必须使用互斥抽屉' })
    }
    if (!contract.keyboard_entry.trim()) issues.push({ field: 'keyboard_entry', message: '缺少键盘入口说明' })
    if (!contract.permission_summary.trim()) issues.push({ field: 'permission_summary', message: '缺少权限说明' })
    const commandIds = new Set(actionIds)
    if (contract.danger_commands.some(command => !commandIds.has(command))) {
        issues.push({ field: 'danger_commands', message: '危险命令必须同时声明在页面操作中' })
    }
    return issues
}
