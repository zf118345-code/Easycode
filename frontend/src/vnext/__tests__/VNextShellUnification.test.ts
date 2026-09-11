import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { Braces, Images } from 'lucide-vue-next'
import { describe, expect, it } from 'vitest'
import VNextActivityRail from '../components/ui/VNextActivityRail.vue'
import ideSource from '../components/VNextIdeV6.vue?raw'
import runConsoleSource from '../program/ProgramRunConsole.vue?raw'
import problemsSource from '../program/ProgramProblemsPanel.vue?raw'
import resourceSource from '../components/VNextResourceWorkspace.vue?raw'
import variableSource from '../components/VNextProjectVariableWorkspace.vue?raw'
import targetSource from '../components/VNextTargetWorkspace.vue?raw'
import playerSource from '../components/VNextPlayerWorkspace.vue?raw'
import replaySource from '../components/VNextReplayWorkspace.vue?raw'
import scheduleSource from '../components/VNextScheduleWorkspace.vue?raw'
import extensionSource from '../components/VNextExtensionWorkspace.vue?raw'
import librarySource from '../program/ProgramFunctionLibrary.vue?raw'
import paneHeaderSource from '../components/ui/VNextPaneHeader.vue?raw'
import navigationPaneSource from '../components/ui/VNextNavigationPane.vue?raw'
import navigationItemSource from '../components/ui/VNextNavigationItem.vue?raw'
import statementSummarySource from '../program/ProgramStatementSummary.vue?raw'
import statementListSource from '../program/ProgramStatementList.vue?raw'

const themeSource = readFileSync(join(process.cwd(), 'src', 'assets', 'theme.css'), 'utf8')

describe('统一开发端外壳', () => {
    it('用同一活动栏数据渲染图标和文字模式', async () => {
        const wrapper = mount(VNextActivityRail, {
            props: {
                mode: 'labeled',
                items: [
                    { id: 'program', label: '函数库', icon: Braces, active: true },
                    { id: 'resources', label: '资源', icon: Images },
                ],
            },
        })
        expect(wrapper.classes()).toContain('is-labeled')
        expect(wrapper.text()).toContain('函数库')
        await wrapper.findAll('button')[1].trigger('click')
        expect(wrapper.emitted('activate')).toEqual([['resources']])
        await wrapper.setProps({ mode: 'compact' })
        expect(wrapper.classes()).toContain('is-compact')
    })

    it('把模式偏好和底部标签集中在 IDE 外壳', () => {
        expect(ideSource).toContain('<VNextActivityRail')
        expect(ideSource).toContain('easycode:vnext:activity-rail-mode')
        expect(ideSource).toContain('<ProgramBottomFeedbackPanel')
        expect(ideSource).not.toContain('<ProgramRunConsole')
        expect(ideSource).not.toContain('<ProgramProblemsPanel')
    })

    it('所有长期左栏共享标题和导航原语，焦点陷阱页保留原生根', () => {
        for (const source of [librarySource, resourceSource, variableSource, targetSource, playerSource, scheduleSource, extensionSource]) {
            expect(source).toContain('<VNextNavigationPane')
            expect(source).toContain('<VNextPaneHeader')
            expect(source).toContain('<VNextNavigationItem')
        }
        expect(replaySource).toContain('<aside')
        expect(replaySource).toContain('<VNextPaneHeader')
        expect(replaySource).toContain('<VNextListSearch')
        expect(replaySource).toContain('<VNextNavigationItem')
        expect(replaySource).toContain('density="multiline"')
        for (const source of [librarySource, resourceSource, variableSource, targetSource, playerSource, replaySource, scheduleSource, extensionSource]) {
            expect(source).toContain('app-navigation-list')
        }
    })

    it('由共享原语唯一持有页头动作、侧栏底色和选中标记几何', () => {
        expect(paneHeaderSource).toContain('.vnext-pane-header__actions :deep(button)')
        expect(paneHeaderSource).toContain('height: var(--app-height-pane-header) !important')
        expect(navigationPaneSource).toContain('padding: 0 !important')
        expect(navigationPaneSource).toContain('background: var(--app-bg-sidebar) !important')
        expect(navigationItemSource).toContain('app-navigation-item')
        expect(themeSource).toContain('.app-navigation-list')
        expect(themeSource).toContain('height: var(--app-list-row-compact) !important')
        expect(themeSource).toContain('.app-navigation-item.is-multiline')
        expect(themeSource).toMatch(/\.app-navigation-item\.is-selected::before[\s\S]+border-radius:\s*0;/)
        expect(themeSource).toMatch(/\.app-navigation-item\.is-selected[\s\S]+box-shadow:\s*none\s*!important;/)
    })

    it('把桌面工作区排版收敛为正文和标题两档', () => {
        expect(themeSource).toContain('--app-font-interface: 13px')
        expect(themeSource).toContain('--app-font-heading: 15px')
        for (const token of ['caption', 'compact', 'body', 'pane-title', 'xs', 'sm']) {
            expect(themeSource).toContain(`--app-font-${token}: var(--app-font-interface)`)
        }
        for (const token of ['page-title', 'md', 'lg', 'xl', '2xl']) {
            expect(themeSource).toContain(`--app-font-${token}: var(--app-font-heading)`)
        }
        expect(paneHeaderSource).toContain('.vnext-pane-header__meta { font-size: var(--app-font-pane-title); }')
        expect(paneHeaderSource).toContain('.vnext-pane-header[data-ui-role="workspace"] .vnext-pane-header__meta { font-size: var(--app-font-page-title); }')
        expect(ideSource).not.toMatch(/font:\s*(?:9|10|11|12|14)px/)
        expect(extensionSource).not.toMatch(/font:\s*(?:9|10|11|12|14)px/)
    })

    it('中央摘要动态值只用半方括号标识并继承同行文字', () => {
        expect(statementSummarySource).toMatch(/\.statement-dynamic-value\s*\{[\s\S]*?color:\s*inherit;/)
        expect(statementSummarySource).toMatch(/\.statement-dynamic-value\s*\{[\s\S]*?font:\s*inherit;/)
        expect(statementSummarySource).toMatch(/\.statement-dynamic-value\s*\{[\s\S]*?letter-spacing:\s*inherit;/)
        expect(statementSummarySource).toMatch(/\.statement-dynamic-value\s*\{[\s\S]*?display:\s*inline-block;/)
        expect(statementSummarySource).toMatch(/\.statement-dynamic-value\s*\{[\s\S]*?line-height:\s*inherit;/)
        expect(statementSummarySource).toMatch(/\.statement-dynamic-value\s*\{[\s\S]*?vertical-align:\s*baseline;/)
        expect(statementSummarySource).not.toMatch(/\.statement-dynamic-value\s*\{[\s\S]*?vertical-align:\s*middle;/)
        expect(statementListSource).toMatch(/\.statement-content\s*\{[\s\S]*?align-items:\s*baseline;/)
        expect(statementListSource).toMatch(/\.statement-content\s*\{[\s\S]*?line-height:\s*var\(--app-line-height-compact\);/)
        expect(statementListSource).toMatch(/\.step-label\s*\{[\s\S]*?line-height:\s*inherit;/)
        expect(statementSummarySource).not.toMatch(/\.statement-dynamic-value\s*\{[\s\S]*?color:\s*var\(--app-text-primary\)/)
    })

    it('把所有左栏标题动作统一投影为可访问的 28px 纯图标', () => {
        expect(navigationPaneSource).toContain(':deep(.vnext-pane-header__actions button)')
        expect(navigationPaneSource).toContain('width: var(--app-control-compact) !important')
        expect(navigationPaneSource).toContain('font-size: 0 !important')
        expect(navigationPaneSource).toContain('button > span) { display: none !important; }')
        expect(navigationPaneSource).toContain('gap: var(--app-spacing-xs) !important')
        expect(paneHeaderSource).toContain('width: 14px !important')
        expect(paneHeaderSource).toContain('button:active:not(:disabled)')
        expect(paneHeaderSource).toContain('background: var(--app-bg-active) !important')
        expect(paneHeaderSource).toContain('opacity: .35')
        expect(paneHeaderSource).toContain('has-icon-only-actions')
        expect(replaySource).toContain('icon-only-actions')

        for (const [source, accessibleName] of [
            [librarySource, '新建项目函数'],
            [variableSource, '新建项目变量'],
            [targetSource, '新建运行目标'],
            [resourceSource, '新建资源文件夹'],
            [playerSource, '新增页面'],
            [replaySource, '刷新会话'],
            [extensionSource, '新建扩展骨架'],
        ]) {
            expect(source).toContain('<VNextIconButton')
            expect(source).toContain(`label="${accessibleName}"`)
        }
    })

    it('底部内容在嵌入模式由唯一外壳持有高度', () => {
        expect(runConsoleSource).toContain('.run-console.embedded { width: 100%; height: 100%;')
        expect(problemsSource).toContain('.problems-panel.embedded { width: 100%; height: 100%;')
        expect(ideSource).toContain("bottomPanelTab = ref<BottomFeedbackTab>('output')")
        expect(ideSource).toContain("'has-notice': bottomPanelOpen && Boolean(notice.message)")
        expect(ideSource).toContain('grid-template-rows: 5px minmax(0, 1fr);')
        expect(ideSource).toContain('.bottom-stack.has-panel.has-notice { grid-template-rows: 5px auto minmax(0, 1fr); }')
    })
})
