<template>
    <el-dialog v-model="dialogVisible"
               :title="isEdit ? '编辑判定条件' : '新增判定条件'"
               width="560px"
               append-to-body
               :z-index="1050"
               :close-on-click-modal="false">
        <el-form label-width="120px" size="small">
            <!-- 1. 条件类型 -->
            <el-form-item label="条件类型">
                <el-select v-model="localCond.condition_type" placeholder="请选择类型" style="width: 100%;">
                    <el-option label="🖼️ 屏幕存在指定图片" value="image_exists" />
                    <el-option label="🔢 变量数值/逻辑比较" value="var_compare" />
                </el-select>
            </el-form-item>

            <!-- 2. 图片匹配条件参数 -->
            <template v-if="localCond.condition_type === 'image_exists'">
                <el-form-item label="模板图片">
                    <ParamRenderer :config="{ type: 'file', label: '模板图片' }"
                                   :value="localCond.params.image_source"
                                   @update="(val) => localCond.params.image_source = val" />
                </el-form-item>
                <el-form-item label="匹配阈值 (%)">
                    <el-input-number v-model="localCond.params.threshold" :min="1" :max="100" />
                </el-form-item>
                <el-form-item label="灰度匹配">
                    <el-switch v-model="localCond.params.gray_scale" />
                </el-form-item>
            </template>

            <!-- 3. 变量比较条件参数 -->
            <template v-if="localCond.condition_type === 'var_compare'">
                <el-form-item label="变量名称">
                    <el-input v-model="localCond.params.var_name" placeholder="请输入变量名，如 run_count" />
                </el-form-item>
                <el-form-item label="比较运算符">
                    <el-select v-model="localCond.params.operator" style="width: 100%;">
                        <el-option label="等于 (=)" value="eq" />
                        <el-option label="不等于 (!=)" value="ne" />
                        <el-option label="大于 (>)" value="gt" />
                        <el-option label="大于等于 (>=)" value="gte" />
                        <el-option label="小于 (<)" value="lt" />
                        <el-option label="小于等于 (<=)" value="lte" />
                    </el-select>
                </el-form-item>
                <el-form-item label="目标比较值">
                    <el-input v-model="localCond.params.target_value" placeholder="如：5 或 true 或 武神殿" />
                </el-form-item>
            </template>

            <!-- 4. ⭐ Branch 节点：成功跳转精准显隐规则 -->
            <template v-if="showJumpConfig">
                <el-divider content-position="left">条件成立时成功跳转</el-divider>
                <el-form-item label="跳转类型">
                    <el-select v-model="localJump.jump_type" style="width: 100%;" @change="onJumpTypeChange">
                        <el-option label="下一个节点" value="next" />
                        <el-option label="跳转节点" value="node" />
                        <el-option label="跳转任务" value="task" />
                        <el-option label="结束流程" value="end" />
                    </el-select>
                </el-form-item>

                <!-- ⭐ 精准显隐 1：仅当跳转类型为 'task' 时，才显示目标任务 -->
                <el-form-item v-if="localJump.jump_type === 'task'" label="目标任务">
                    <el-select v-model="localJump.target_task" style="width: 100%;" @change="onTaskChange">
                        <el-option v-for="t in store.tasks"
                                   :key="t.task_id"
                                   :label="t.task_name || t.task_id"
                                   :value="t.task_id" />
                    </el-select>
                </el-form-item>

                <!-- ⭐ 精准显隐 2：仅当跳转类型为 'node' 或 'task' 时，才显示目标节点 -->
                <el-form-item v-if="localJump.jump_type === 'node' || localJump.jump_type === 'task'" label="目标节点">
                    <el-select v-model="localJump.target_node" style="width: 100%;">
                        <el-option v-for="(n, idx) in availableNodes"
                                   :key="n.node_id"
                                   :label="`${idx + 1}. ${n.node_name || n.node_id}`"
                                   :value="n.node_id" />
                    </el-select>
                </el-form-item>
            </template>
        </el-form>

        <template #footer>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" @click="confirmSave">确定保存</el-button>
        </template>
    </el-dialog>
</template>

<script>
    import { ref, computed, watch, defineAsyncComponent } from 'vue'
    import { useMainStore } from '@/stores'

    export default {
        name: 'ConditionDialog',
        components: {
            ParamRenderer: defineAsyncComponent(() => import('@/components/ParamRenderer.vue'))
        },
        props: {
            visible: Boolean,
            showJumpConfig: { type: Boolean, default: false },
            initialData: Object
        },
        emits: ['update:visible', 'save'],
        setup(props, { emit }) {
            const store = useMainStore()
            const availableNodes = ref([])

            const localCond = ref({
                condition_type: 'image_exists',
                params: { image_source: '', threshold: 85, gray_scale: true, var_name: '', operator: 'eq', target_value: '' }
            })

            const localJump = ref({ jump_type: 'next', target_task: '', target_node: '' })
            const isEdit = ref(false)

            const dialogVisible = computed({
                get: () => props.visible,
                set: (val) => emit('update:visible', val)
            })

            watch(() => props.visible, async (val) => {
                if (val) {
                    if (props.initialData) {
                        isEdit.value = true
                        localCond.value = JSON.parse(JSON.stringify(props.initialData.condition || props.initialData))
                        if (props.showJumpConfig) {
                            // ⭐ 加载数据时强制兼容字段 jump_type / type
                            const rawJump = props.initialData.on_success || {}
                            localJump.value = {
                                jump_type: rawJump.jump_type || rawJump.type || 'next',
                                target_task: rawJump.target_task || rawJump.target || '',
                                target_node: rawJump.target_node || ''
                            }
                        }
                    } else {
                        isEdit.value = false
                        localCond.value = {
                            condition_type: 'image_exists',
                            params: { image_source: '', threshold: 85, gray_scale: true, var_name: '', operator: 'eq', target_value: '' }
                        }
                        localJump.value = { jump_type: 'next', target_task: '', target_node: '' }
                    }
                    await updateAvailableNodes()
                }
            })

            // 动态拉取与更新可选择节点列表
            const updateAvailableNodes = async () => {
                if (localJump.value.jump_type === 'node') {
                    availableNodes.value = store.nodes || []
                } else if (localJump.value.jump_type === 'task' && localJump.value.target_task) {
                    if (localJump.value.target_task === store.currentTaskId) {
                        availableNodes.value = store.nodes || []
                    } else {
                        availableNodes.value = await store.loadTaskNodes(localJump.value.target_task)
                    }
                } else {
                    availableNodes.value = []
                }
            }

            // ⭐ 切换【跳转类型】智能联动与清空
            const onJumpTypeChange = async (val) => {
                if (val === 'next' || val === 'end') {
                    localJump.value.target_task = ''
                    localJump.value.target_node = ''
                } else if (val === 'node') {
                    localJump.value.target_task = ''
                    const currentNodes = store.nodes || []
                    if (currentNodes.length > 0) {
                        localJump.value.target_node = currentNodes[0].node_id
                    } else {
                        localJump.value.target_node = ''
                    }
                } else if (val === 'task') {
                    const targetTaskId = store.currentTaskId || (store.tasks.length ? store.tasks[0].task_id : '')
                    localJump.value.target_task = targetTaskId
                    if (targetTaskId) {
                        const nodes = await store.loadTaskNodes(targetTaskId)
                        localJump.value.target_node = (nodes && nodes.length > 0) ? nodes[0].node_id : ''
                    } else {
                        localJump.value.target_node = ''
                    }
                }
                await updateAvailableNodes()
            }

            // ⭐ 切换【目标任务】智能联动
            const onTaskChange = async (taskId) => {
                if (taskId) {
                    const nodes = await store.loadTaskNodes(taskId)
                    localJump.value.target_node = (nodes && nodes.length > 0) ? nodes[0].node_id : ''
                } else {
                    localJump.value.target_node = ''
                }
                await updateAvailableNodes()
            }

            const confirmSave = () => {
                emit('save', {
                    condition: localCond.value,
                    on_success: props.showJumpConfig ? localJump.value : undefined
                })
                dialogVisible.value = false
            }

            return { store, dialogVisible, localCond, localJump, isEdit, availableNodes, onJumpTypeChange, onTaskChange, confirmSave }
        }
    }
</script>

<style scoped>
    /* 条件对话框内部表单排版精修 */
    :deep(.el-form-item__label) {
        color: var(--el-text-color-regular) !important;
        font-weight: 500;
    }

    .dialog-divider {
        margin: 16px 0 12px 0;
        border-color: var(--el-border-color-light);
    }

    .jump-config-box {
        background: var(--el-fill-color-blank);
        border: 1px solid var(--el-border-color-light);
        border-radius: 8px;
        padding: 12px;
        margin-top: 8px;
    }
</style>