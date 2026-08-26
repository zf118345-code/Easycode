import { computed, ref } from 'vue'
import { capabilityApi } from '@/api/capabilityApi'

const capabilities = ref([])
const errors = ref([])
const loading = ref(false)
let loadedWorkspace = ''
let pending = null

export function useCapabilityCatalog(projectPath) {
    const load = async (force = false) => {
        const path = typeof projectPath === 'function' ? projectPath() : projectPath?.value
        if (!path) {
            capabilities.value = []
            errors.value = []
            loadedWorkspace = ''
            return
        }
        if (!force && loadedWorkspace === path && capabilities.value.length) return
        if (pending && !force) return pending
        loading.value = true
        pending = capabilityApi.list(force)
            .then(result => {
                capabilities.value = Array.isArray(result?.capabilities) ? result.capabilities : []
                errors.value = Array.isArray(result?.errors) ? result.errors : []
                loadedWorkspace = path
            })
            .finally(() => {
                loading.value = false
                pending = null
            })
        return pending
    }

    const find = id => capabilities.value.find(item => item.id === id) || null
    return {
        capabilities: computed(() => capabilities.value),
        errors: computed(() => errors.value),
        loading: computed(() => loading.value),
        load,
        find
    }
}
