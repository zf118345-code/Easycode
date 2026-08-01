<template>
    <div class="task-list-panel">
        <div class="panel-header">
            <span>任务列表</span>
            <el-button type="primary" size="small" circle @click="showNewTaskDialog">
                <el-icon><Plus /></el-icon>
            </el-button>
        </div>

        <draggable v-model="sortedTasks"
                   item-key="task_id"
                   class="task-list"
                   handle=".drag-handle"
                   @end="onDragEnd">
            <template #item="{ element: task }">
                <div class="task-card"
                     :class="{ active: store.currentTaskId === task.task_id }"
                     @click="selectTask(task.task_id)">
                    <!-- 第一行：任务名称 + 操作按钮 -->
                    <div class="task-row">
                        <div class="task-name-area">
                            <span v-if="editingName !== task.task_id" class="task-name" @dblclick="startEditName(task)">
                                {{ task.task_name }}
                            </span>
                            <el-input v-else
                                      v-model="editNameValue"
                                      size="small"
                                      maxlength="10"
                                      @blur="finishEditName(task)"
                                      @keyup.enter="finishEditName(task)"
                                      class="inline-input"
                                      ref="nameInput" />
                            <el-button link
                                       size="small"
                                       class="edit-icon"
                                       @click.stop="startEditName(task)">
                                <el-icon><Edit /></el-icon>
                            </el-button>
                        </div>
                        <div class="task-actions">
                            <el-button link size="small" class="action-icon play-btn" @click.stop="runTask(task.task_id)">
                                <el-icon><VideoPlay /></el-icon>
                            </el-button>
                            <el-dropdown trigger="click" @command="(cmd) => handleMenuCommand(cmd, task)">
                                <el-button link size="small" class="action-icon menu-btn">
                                    <el-icon><More /></el-icon>
                                </el-button>
                                <template #dropdown>
                                    <el-dropdown-menu>
                                        <el-dropdown-item command="rename">重命名</el-dropdown-item>
                                        <el-dropdown-item command="export">导出任务</el-dropdown-item>
                                        <el-dropdown-item divided command="delete">删除任务</el-dropdown-item>
                                    </el-dropdown-menu>
                                </template>
                            </el-dropdown>
                            <el-icon class="drag-handle"><Rank /></el-icon>
                        </div>
                    </div>

                    <!-- 第二行：间隔（左） + 循环（右） -->
                    <div class="task-meta-row">
                        <div class="meta-item meta-left">
                            <span class="meta-label">间隔：</span>
                            <span v-if="editingInterval !== task.task_id" class="meta-value" @dblclick="startEditInterval(task)">
                                {{ task.loop_interval || 0 }} ms
                            </span>
                            <el-input v-else
                                      v-model="editIntervalValue"
                                      size="small"
                                      type="number"
                                      @blur="finishEditInterval(task)"
                                      @keyup.enter="finishEditInterval(task)"
                                      class="inline-input"
                                      ref="intervalInput" />
                            <el-button link
                                       size="small"
                                       class="meta-edit-icon"
                                       @click.stop="startEditInterval(task)">
                                <el-icon><Edit /></el-icon>
                            </el-button>
                        </div>
                        <div class="meta-item meta-right">
                            <span class="meta-label">循环：</span>
                            <span v-if="editingLoop !== task.task_id" class="meta-value" @dblclick="startEditLoop(task)">
                                {{ task.loop_count === -1 ? '无限' : (task.loop_count ?? 1) + ' 次' }}
                            </span>
                            <el-input v-else
                                      v-model="editLoopValue"
                                      size="small"
                                      type="number"
                                      @blur="finishEditLoop(task)"
                                      @keyup.enter="finishEditLoop(task)"
                                      class="inline-input"
                                      ref="loopInput" />
                            <el-button link
                                       size="small"
                                       class="meta-edit-icon"
                                       @click.stop="startEditLoop(task)">
                                <el-icon><Edit /></el-icon>
                            </el-button>
                        </div>
                    </div>
                </div>
            </template>
        </draggable>

        <div v-if="!sortedTasks.length" class="empty">暂无任务</div>

        <el-dialog title="新建任务" v-model="dialogVisible" width="400px" append-to-body>
            <el-form>
                <el-form-item label="任务名称">
                    <el-input v-model="newTaskName" placeholder="最多10个字符" maxlength="10" @keyup.enter="confirmNewTask" />
                </el-form-item>
            </el-form>
            <template #footer>
                <el-button @click="dialogVisible = false">取消</el-button>
                <el-button type="primary" @click="confirmNewTask">创建</el-button>
            </template>
        </el-dialog>
    </div>
</template>

<script>
    import draggable from 'vuedraggable'
    import { useMainStore } from '@/stores'
    import { ElMessage, ElMessageBox } from 'element-plus'
    import axios from 'axios'
    import { Plus, Edit, VideoPlay, More, Rank } from '@element-plus/icons-vue'

    export default {
        components: { draggable, Plus, Edit, VideoPlay, More, Rank },
        setup() {
            const store = useMainStore()
            return { store }
        },
        data() {
            return {
                dialogVisible: false,
                newTaskName: '',
                editingName: null,
                editNameValue: '',
                editingInterval: null,
                editIntervalValue: '',
                editingLoop: null,
                editLoopValue: '',
            }
        },
        computed: {
            sortedTasks: {
                get() {
                    const order = this.store.taskOrder || []
                    if (order.length) {
                        const tasksCopy = [...this.store.tasks]
                        tasksCopy.sort((a, b) => {
                            const idxA = order.indexOf(a.task_id)
                            const idxB = order.indexOf(b.task_id)
                            return (idxA === -1 ? 999 : idxA) - (idxB === -1 ? 999 : idxB)
                        })
                        return tasksCopy
                    }
                    return this.store.tasks || []
                },
                set(value) {
                    this.store.tasks.splice(0, this.store.tasks.length, ...value)
                    this.store.taskOrder = value.map(t => t.task_id)
                }
            }
        },
        methods: {
            // ⭐ 保证切换任务时，毫无阻碍地调取数据并拉取关联节点
            async selectTask(taskId) {
                await this.store.loadTaskData(taskId)
            },

            // ====== 通用持久化当前 Task 变动 ======
            async persistTaskChange(taskObj) {
                try {
                    // 1. 如果修改的恰好是当前高亮选中的任务，同步 store.currentTaskData
                    if (taskObj.task_id === this.store.currentTaskId && this.store.currentTaskData) {
                        this.store.currentTaskData.task_name = taskObj.task_name
                        this.store.currentTaskData.loop_interval = taskObj.loop_interval
                        this.store.currentTaskData.loop_count = taskObj.loop_count
                    }

                    // 2. 获取该任务在后端的完整定义并覆盖更新属性
                    const res = await axios.get(`/api/tasks/${taskObj.task_id}`, {
                        params: { project_path: this.store.currentProjectPath }
                    })
                    const fullTaskData = res.data
                    fullTaskData.task_name = taskObj.task_name
                    fullTaskData.loop_interval = taskObj.loop_interval
                    fullTaskData.loop_count = taskObj.loop_count

                    // 3. 保存至磁盘
                    await this.store.saveTaskData(fullTaskData)
                    ElMessage.success('任务属性更新成功')
                } catch (err) {
                    ElMessage.error('更新任务属性失败')
                }
            },

            // ====== 内联编辑名称 ======
            startEditName(task) {
                this.editingName = task.task_id
                this.editNameValue = task.task_name
                this.$nextTick(() => {
                    const input = this.$refs.nameInput
                    if (input) input.focus()
                })
            },
            async finishEditName(task) {
                const name = this.editNameValue.trim()
                if (name.length > 10) {
                    ElMessage.warning('任务名称不能超过10个字符')
                    this.editingName = null
                    return
                }
                if (name && name !== task.task_name) {
                    task.task_name = name
                    await this.persistTaskChange(task)
                }
                this.editingName = null
            },

            // ====== 内联编辑间隔 ======
            startEditInterval(task) {
                this.editingInterval = task.task_id
                this.editIntervalValue = task.loop_interval || 0
                this.$nextTick(() => {
                    const input = this.$refs.intervalInput
                    if (input) input.focus()
                })
            },
            async finishEditInterval(task) {
                let val = parseInt(this.editIntervalValue)
                if (isNaN(val) || val < 0) val = 0
                if (val !== task.loop_interval) {
                    task.loop_interval = val
                    await this.persistTaskChange(task)
                }
                this.editingInterval = null
            },

            // ====== 内联编辑循环次数 ======
            startEditLoop(task) {
                this.editingLoop = task.task_id
                this.editLoopValue = task.loop_count
                this.$nextTick(() => {
                    const input = this.$refs.loopInput
                    if (input) input.focus()
                })
            },
            async finishEditLoop(task) {
                let val = parseInt(this.editLoopValue)
                if (isNaN(val) || val < -1) val = 1
                if (val !== task.loop_count) {
                    task.loop_count = val
                    await this.persistTaskChange(task)
                }
                this.editingLoop = null
            },

            async deleteTask(taskId) {
                const targetId = taskId || this.store.currentTaskId
                if (!targetId) return
                try {
                    await ElMessageBox.confirm('确定要删除当前任务吗？', '确认删除', { type: 'warning' })
                    await this.store.deleteTask(targetId)
                    ElMessage.success('任务已删除')
                } catch (err) {
                    if (err !== 'cancel') {
                        ElMessage.error('删除失败: ' + (err.message || '未知错误'))
                    }
                }
            },

            showNewTaskDialog() {
                this.newTaskName = ''
                this.dialogVisible = true
            },
            async confirmNewTask() {
                const name = this.newTaskName.trim()
                if (!name) {
                    ElMessage.warning('请输入任务名称')
                    return
                }
                if (name.length > 10) {
                    ElMessage.warning('任务名称不能超过10个字符')
                    return
                }
                try {
                    await this.store.createNewTask(name)
                    ElMessage.success('任务创建成功')
                    this.dialogVisible = false
                } catch (err) {
                    ElMessage.error(err.message || '创建失败')
                }
            },

            handleMenuCommand(command, task) {
                switch (command) {
                    case 'rename':
                        this.startEditName(task)
                        break
                    case 'export':
                        ElMessage.info('导出任务')
                        break
                    case 'delete':
                        this.deleteTask(task.task_id)
                        break
                }
            },

            async runTask(taskId) {
                try {
                    ElMessage.info('任务执行中...')
                    const result = await this.store.runTask(taskId, null)
                    if (result.status === 'started') {
                        ElMessage.success('任务已启动，请查看执行状态')
                    } else {
                        ElMessage.error('执行失败: ' + (result.message || '未知错误'))
                    }
                } catch (err) {
                    ElMessage.error('执行请求失败: ' + (err.message || '未知错误'))
                }
            },

            async onDragEnd() {
                const order = this.store.tasks.map(t => t.task_id)
                await this.store.saveTaskOrder(order)
                ElMessage.success('任务顺序已保存')
            }
        }
    }
</script>

<style scoped>
    .task-list-panel {
        display: flex;
        flex-direction: column;
        height: 100%;
        background: #282a3a;
        border-radius: 4px;
        overflow: hidden;
    }

    .panel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        height: 36px;
        padding: 0 12px;
        background: #32324a;
        color: #cfd3e6;
        font-weight: 500;
        font-size: 13px;
        border-bottom: 1px solid #3d3d5a;
        flex-shrink: 0;
    }

    .task-list {
        flex: 1;
        list-style: none;
        margin: 0;
        padding: 4px 0;
        overflow-y: auto;
    }

    .task-card {
        background: #3d3d5a;
        margin: 4px 8px;
        padding: 8px 12px;
        border-radius: 4px;
        border: 1px solid transparent;
        cursor: pointer;
        transition: border-color 0.2s, background 0.2s;
    }

        .task-card.active {
            border-color: #409EFF;
            background: #4a4a6a;
        }

    .task-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 4px;
    }

    .task-name-area {
        display: flex;
        align-items: center;
        gap: 6px;
        flex: 1;
    }

    .task-name {
        color: #cfd3e6;
        font-size: 14px;
        font-weight: 500;
    }

    .task-actions {
        display: flex;
        align-items: center;
        gap: 2px;
    }

    .action-icon {
        color: #8a8fa8;
        padding: 4px;
        opacity: 0.5;
        transition: opacity 0.2s;
    }

        .action-icon:hover {
            color: #cfd3e6;
        }

    .play-btn:hover {
        color: #67c23a;
    }

    .menu-btn:hover {
        color: #e6a23c;
    }

    .drag-handle {
        cursor: grab;
        color: #6a6a8a;
        font-size: 18px;
    }

        .drag-handle:hover {
            color: #cfd3e6;
        }

    .task-meta-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 12px;
        color: #8a8fa8;
        margin-top: 2px;
    }

    .meta-item {
        display: flex;
        align-items: center;
        gap: 4px;
    }

    .meta-label {
        color: #6a6a8a;
    }

    .meta-value {
        color: #cfd3e6;
        cursor: default;
    }

    .inline-input {
        width: 50px;
        height: 22px;
    }

        .inline-input .el-input__inner {
            height: 22px;
            padding: 0 4px;
            font-size: 12px;
        }

    .edit-icon,
    .meta-edit-icon {
        padding: 0;
        font-size: 12px;
        color: #8a8fa8;
        opacity: 0;
        transition: opacity 0.2s ease;
    }

    .task-card:hover .edit-icon,
    .task-card:hover .meta-edit-icon {
        opacity: 1;
    }

    .edit-icon:hover,
    .meta-edit-icon:hover {
        color: #cfd3e6;
    }

    .empty {
        flex: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #8a8fa8;
    }
</style>