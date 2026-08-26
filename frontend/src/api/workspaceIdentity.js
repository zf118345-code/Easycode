let activeIdentity = null

export function setWorkspaceIdentity(workspace) {
    if (!workspace?.workspace_id || workspace?.generation === undefined) {
        activeIdentity = null
        return
    }
    activeIdentity = {
        workspaceId: workspace.workspace_id,
        generation: Number(workspace.generation)
    }
}

export function getWorkspaceIdentity() {
    return activeIdentity ? { ...activeIdentity } : null
}

export function workspaceHeaders(identity = activeIdentity) {
    if (!identity?.workspaceId || identity?.generation === undefined) return {}
    return {
        'X-Workspace-Id': identity.workspaceId,
        'X-Workspace-Generation': String(identity.generation)
    }
}

