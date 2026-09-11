import { VNextApiError } from './api'
import type {
    ExtensionPackage,
    ExtensionPackagesResponse,
    ExtensionReference,
    ExtensionScope,
    ExtensionWorkspaceIdentity,
} from './extensionTypes'

function headers(workspace: ExtensionWorkspaceIdentity): Record<string, string> {
    return {
        'Content-Type': 'application/json',
        'X-Workspace-Id': workspace.workspace_id,
        'X-Workspace-Generation': String(workspace.generation),
    }
}

async function call<T>(
    workspace: ExtensionWorkspaceIdentity,
    url: string,
    init: RequestInit = {},
): Promise<T> {
    const response = await fetch(url, { ...init, headers: { ...headers(workspace), ...(init.headers || {}) } })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
        const detail = payload?.detail && typeof payload.detail === 'object' ? payload.detail : null
        const message = typeof payload?.detail === 'string'
            ? payload.detail
            : String(detail?.message || payload?.message || `请求失败 (${response.status})`)
        throw new VNextApiError(message, response.status, String(detail?.error_id || ''), String(detail?.code || ''))
    }
    return payload as T
}

const scopeBody = (scope: ExtensionScope) => JSON.stringify({ scope })
const packageUrl = (packageId: string) => `/api/vnext/extensions/${encodeURIComponent(packageId)}`

export const extensionApi = {
    list: (workspace: ExtensionWorkspaceIdentity) =>
        call<ExtensionPackagesResponse>(workspace, '/api/vnext/extensions'),
    detail: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: ExtensionScope) =>
        call<ExtensionPackage>(workspace, `${packageUrl(packageId)}?scope=${scope}`),
    scaffold: (workspace: ExtensionWorkspaceIdentity, payload: {
        package_id: string
        publisher_id: string
        publisher_name: string
        display_name: string
        description: string
        scope: 'project' | 'user'
    }) => call<{ created: true; package: ExtensionPackage }>(workspace, '/api/vnext/extensions/scaffold', {
        method: 'POST', body: JSON.stringify(payload),
    }),
    importFolder: (workspace: ExtensionWorkspaceIdentity, sourcePath: string, scope: 'project' | 'user') =>
        call<{ imported: true; package: ExtensionPackage }>(workspace, '/api/vnext/extensions/import', {
            method: 'POST', body: JSON.stringify({ source_path: sourcePath, scope }),
        }),
    validate: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: ExtensionScope) =>
        call<Record<string, unknown>>(workspace, `${packageUrl(packageId)}/validate`, { method: 'POST', body: scopeBody(scope) }),
    references: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: ExtensionScope) =>
        call<{ package_id: string; scope: ExtensionScope; references: ExtensionReference[] }>(
            workspace, `${packageUrl(packageId)}/references`, { method: 'POST', body: scopeBody(scope) },
        ),
    trust: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: 'project' | 'user') =>
        call<Record<string, unknown>>(workspace, `${packageUrl(packageId)}/trust`, {
            method: 'POST', body: JSON.stringify({ scope, mode: 'explicit' }),
        }),
    untrust: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: 'project' | 'user') =>
        call<Record<string, unknown>>(workspace, `${packageUrl(packageId)}/trust?scope=${scope}`, { method: 'DELETE' }),
    enable: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: ExtensionScope) =>
        call<Record<string, unknown>>(workspace, `${packageUrl(packageId)}/enable`, { method: 'POST', body: scopeBody(scope) }),
    disable: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: ExtensionScope) =>
        call<Record<string, unknown>>(workspace, `${packageUrl(packageId)}/disable`, { method: 'POST', body: scopeBody(scope) }),
    build: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: ExtensionScope) =>
        call<Record<string, unknown>>(workspace, `${packageUrl(packageId)}/build`, { method: 'POST', body: scopeBody(scope) }),
    sealAndroidJvm: (
        workspace: ExtensionWorkspaceIdentity,
        packageId: string,
        scope: 'project' | 'user',
        variantId: string,
        modulePath: string,
    ) => call<Record<string, unknown>>(workspace, `${packageUrl(packageId)}/seal-android-jvm`, {
        method: 'POST', body: JSON.stringify({ scope, variant_id: variantId, module_path: modulePath }),
    }),
    openFolder: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: ExtensionScope) =>
        call<Record<string, unknown>>(workspace, `${packageUrl(packageId)}/open`, { method: 'POST', body: scopeBody(scope) }),
    runTests: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: ExtensionScope) =>
        call<{ passed: boolean; total: number; tests: Array<Record<string, unknown>> }>(
            workspace, `${packageUrl(packageId)}/contract-tests`, { method: 'POST', body: scopeBody(scope) },
        ),
    delete: (workspace: ExtensionWorkspaceIdentity, packageId: string, scope: 'project' | 'user') =>
        call<Record<string, unknown>>(workspace, `${packageUrl(packageId)}?scope=${scope}`, { method: 'DELETE' }),
}
