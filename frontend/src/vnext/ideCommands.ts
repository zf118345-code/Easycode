export type IdeCommandGroup = '项目' | '编辑' | '视图' | '运行' | '帮助'

export interface IdeCommandDefinition {
    id: string
    group: IdeCommandGroup
    label: string
    description: string
    shortcut?: boolean
}

export const IDE_COMMANDS: IdeCommandDefinition[] = [
    { id: 'project.new', group: '项目', label: '新建项目', description: '在新的空白目录中创建 EasyCode 项目' },
    { id: 'project.open', group: '项目', label: '打开项目', description: '选择并切换到另一个 EasyCode 项目' },
    { id: 'project.new_function', group: '项目', label: '新建项目函数', description: '在当前项目中新建一个结构化函数' },
    { id: 'project.history', group: '项目', label: '历史版本', description: '查看和恢复当前函数的历史版本' },
    { id: 'edit.undo', group: '编辑', label: '撤销', description: '撤销上一次结构化修改', shortcut: true },
    { id: 'edit.redo', group: '编辑', label: '重做', description: '恢复刚才撤销的修改', shortcut: true },
    { id: 'edit.find', group: '编辑', label: '查找当前函数', description: '按名称、备注或语句 ID 查找', shortcut: true },
    { id: 'edit.copy_statements', group: '编辑', label: '复制语句', description: '复制选中语句，可粘贴到当前项目的其他函数', shortcut: true },
    { id: 'edit.cut_statements', group: '编辑', label: '剪切语句', description: '标记选中语句，粘贴时再移动', shortcut: true },
    { id: 'edit.paste_statements', group: '编辑', label: '粘贴语句', description: '在当前语句或分支之后粘贴', shortcut: true },
    { id: 'edit.duplicate_statement', group: '编辑', label: '创建语句副本', description: '在原位置后复制一份选中语句', shortcut: true },
    { id: 'edit.delete_statement', group: '编辑', label: '删除选中语句', description: '删除当前选中的一条或多条语句', shortcut: true },
    { id: 'edit.extract_function', group: '编辑', label: '提取为项目函数', description: '把连续选中的语句提取为新函数', shortcut: true },
    { id: 'view.program', group: '视图', label: '程序', description: '打开结构化程序工作区' },
    { id: 'view.resources', group: '视图', label: '资源', description: '打开资源工作区' },
    { id: 'view.variables', group: '视图', label: '项目变量', description: '打开项目变量工作区' },
    { id: 'view.targets', group: '视图', label: '运行目标', description: '打开运行目标工作区' },
    { id: 'view.player', group: '视图', label: 'Player 界面', description: '编辑 Player 页面与字段' },
    { id: 'view.replay', group: '视图', label: '运行记录', description: '查看录制时间线与历史帧' },
    { id: 'view.extensions', group: '视图', label: '扩展', description: '查看项目使用的扩展能力' },
    { id: 'view.schedules', group: '视图', label: '计划与实例', description: '管理本地计划和实例调度' },
    { id: 'view.toggle_problems', group: '视图', label: '运行与检查：问题', description: '打开统一反馈面板中的问题页', shortcut: true },
    { id: 'view.toggle_log', group: '视图', label: '运行与检查：输出', description: '打开统一反馈面板中的输出页', shortcut: true },
    { id: 'view.toggle_activity_labels', group: '视图', label: '切换导航显示方式', description: '在图标导航和图标加文字导航之间切换' },
    { id: 'view.reset_layout', group: '视图', label: '重置面板布局', description: '恢复侧栏、详情和底部面板的默认尺寸' },
    { id: 'run.check', group: '运行', label: '检查当前函数', description: '检查并编译当前函数' },
    { id: 'run.start_or_resume', group: '运行', label: '运行或继续', description: '开始运行，暂停时继续', shortcut: true },
    { id: 'run.pause', group: '运行', label: '暂停', description: '在安全点暂停当前运行' },
    { id: 'run.step', group: '运行', label: '单步执行', description: '暂停后执行下一条语句', shortcut: true },
    { id: 'run.stop', group: '运行', label: '停止', description: '停止当前运行' },
    { id: 'run.toggle_breakpoint', group: '运行', label: '切换断点', description: '在选中语句设置或取消断点', shortcut: true },
    { id: 'help.command_palette', group: '帮助', label: '搜索并运行命令', description: '搜索全部工作区与操作命令', shortcut: true },
    { id: 'help.getting_started', group: '帮助', label: '使用入门', description: '查看从目标、素材到 Player 的推荐工作流' },
    { id: 'help.shortcuts', group: '帮助', label: '键盘快捷键', description: '查看并修改当前用户的快捷键' },
]

export const FALLBACK_IDE_SHORTCUTS: Record<string, string> = {
    'edit.undo': 'Ctrl+Z',
    'edit.redo': 'Ctrl+Y',
    'edit.find': 'Ctrl+F',
    'edit.copy_statements': 'Ctrl+C',
    'edit.cut_statements': 'Ctrl+X',
    'edit.paste_statements': 'Ctrl+V',
    'edit.duplicate_statement': 'Ctrl+D',
    'edit.delete_statement': 'Delete',
    'edit.extract_function': 'Ctrl+Shift+E',
    'run.start_or_resume': 'F5',
    'run.step': 'F10',
    'run.toggle_breakpoint': 'F9',
    'view.toggle_problems': 'Ctrl+Shift+M',
    'view.toggle_log': 'Ctrl+J',
    'help.command_palette': 'Ctrl+Shift+P',
}

export function shortcutFromKeyboardEvent(event: KeyboardEvent): string {
    const aliases: Record<string, string> = { ' ': 'Space', Esc: 'Escape', Del: 'Delete', Control: '', Shift: '', Alt: '', Meta: '' }
    let key = aliases[event.key] ?? event.key
    if (!key) return ''
    if (key.length === 1) key = key.toUpperCase()
    const parts: string[] = []
    if (event.ctrlKey) parts.push('Ctrl')
    if (event.altKey) parts.push('Alt')
    if (event.shiftKey) parts.push('Shift')
    if (event.metaKey) parts.push('Meta')
    parts.push(key)
    return parts.join('+')
}

export function shortcutMatches(event: KeyboardEvent, shortcut: string): boolean {
    return Boolean(shortcut) && shortcutFromKeyboardEvent(event).toLocaleLowerCase() === shortcut.toLocaleLowerCase()
}
