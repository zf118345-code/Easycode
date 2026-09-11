import type { WorkspaceIdentity } from './types'

export type ExtensionScope = 'official' | 'user' | 'project'

export interface ExtensionDiagnostic {
    code: string
    severity: 'error' | 'warning' | 'info'
    message: string
}

export interface ExtensionFunctionContract {
    function_id: string
    qualified_name: string
    description: string
    contract_version: string
    parameters: Array<{
        parameter_id: string
        name: string
        display_name: string
        value_type: string
        required: boolean
    }>
    return_type: string
    targets: string[]
    permissions: string[]
    timeout_ms: number
}

export interface ExtensionHostVariant {
    variant_id: string
    host: 'windows' | 'android_native'
    runtime: string
    minimum_android_api?: number
    targets: string[]
    development_entry?: string
    entrypoints: Record<string, string>
    artifact?: { path: string; format: 'ecx-runtime-1'; sha256: string; signature: string }
}

export interface ExtensionReference {
    path: string
    json_path: string
    identifier: string
}

export interface ExtensionPackage {
    package_id: string
    display_name: string
    description?: string
    version?: string
    tier?: 'function' | 'feature' | 'target_driver'
    publisher?: { publisher_id: string; display_name: string }
    scope: ExtensionScope
    path: string
    valid: boolean
    signature_verified: boolean
    trusted: boolean
    enabled: boolean
    lock_current: boolean
    trust?: { mode: string; publisher_id: string; trusted_at?: string } | null
    permissions: string[]
    network?: { level: 'none' | 'local_lan' | 'public'; rules: Array<Record<string, unknown>> }
    dependencies: Array<{ package_id: string; version: string; optional: boolean }>
    contributions: Array<{ contribution_id: string; kind: string; path: string; sha256: string }>
    function_contracts: ExtensionFunctionContract[]
    host_variants: ExtensionHostVariant[]
    sealed_artifacts: Array<Record<string, unknown>>
    diagnostics: ExtensionDiagnostic[]
    manifest?: Record<string, unknown>
}

export interface ExtensionPackagesResponse {
    schema_version: 1
    packages: ExtensionPackage[]
    scopes: Array<{ scope: ExtensionScope; path: string; writable: boolean }>
    worker_notice: string
}

export type ExtensionWorkspaceIdentity = WorkspaceIdentity
