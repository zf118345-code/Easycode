<template>
    <section class="variables-panel">
        <div class="variables-toolbar">
            <label class="variable-search"><Search :size="14" /><input v-model="query" placeholder="搜索变量、表达式或说明" /><button v-if="query" type="button" title="清空搜索" @click="query = ''"><X :size="13" /></button></label>
            <button type="button" class="toolbar-button primary" title="新建变量" @click="openCreateDialog"><Plus :size="15" /></button>
            <el-dropdown trigger="click" @command="handleToolbarCommand"><button type="button" class="toolbar-button" title="更多操作"><MoreHorizontal :size="15" /></button><template #dropdown><el-dropdown-menu><el-dropdown-item command="clear-unused" :disabled="unusedVarCount === 0"><Trash2 :size="14" />清理未引用变量（{{ unusedVarCount }}）</el-dropdown-item></el-dropdown-menu></template></el-dropdown>
        </div>

        <div v-if="!query" class="variable-tabs" role="tablist" aria-label="变量分类">
            <button v-for="tab in tabs" :key="tab.id" type="button" role="tab" :aria-selected="activeTab === tab.id" :class="{ active: activeTab === tab.id }" @click="activeTab = tab.id"><span>{{ tab.label }}</span><small v-if="tab.count !== null">{{ tab.count }}</small></button>
        </div>
        <div v-else class="search-summary">跨分类结果 <strong>{{ visibleRows.length }}</strong></div>

        <div class="variable-list">
            <div
                v-for="row in visibleRows"
                :key="`${row.kind}:${row.key}`"
                class="variable-row"
                :tabindex="row.kind === 'user' ? 0 : -1"
                :role="row.kind === 'user' ? 'button' : undefined"
                @keydown.enter="row.kind === 'user' && openEditDialog(row.source)"
                @dblclick="row.kind === 'user' && openEditDialog(row.source)">
                <div class="row-main"><code>{{ row.expression }}</code><span class="source-tag">{{ sourceLabels[row.kind] }}</span><span v-if="row.type" class="type-tag">{{ row.type }}</span></div>
                <div class="row-detail"><span :title="row.value">{{ row.value }}</span><small :title="row.description">{{ row.description }}</small></div>
                <div class="row-actions">
                    <button type="button" title="复制表达式" @click.stop="copyExpression(row.expression)"><Copy :size="13" /></button>
                    <button v-if="row.kind === 'user'" type="button" title="编辑变量" @click.stop="openEditDialog(row.source)"><Pencil :size="13" /></button>
                    <button v-if="row.kind === 'user'" type="button" class="danger" title="删除变量" @click.stop="handleDeleteVar(row.key)"><Trash2 :size="13" /></button>
                </div>
            </div>
            <div v-if="!visibleRows.length" class="empty-state"><strong>{{ query ? '没有匹配变量' : emptyLabel }}</strong><span>{{ query ? '尝试名称、表达式或说明中的其他关键词。' : emptyHint }}</span><button v-if="activeTab === 'user' && !query" type="button" @click="openCreateDialog">新建变量</button></div>
        </div>

        <el-dialog v-model="varDialogVisible" width="480px" append-to-body destroy-on-close :close-on-click-modal="false">
            <template #header><div class="dialog-heading"><Pencil v-if="isEditing" :size="16" /><Plus v-else :size="16" /><span>{{ isEditing ? '编辑全局变量' : '新建全局变量' }}</span></div></template>
            <div class="dialog-form-body"><ParamRenderer v-for="(schema, field) in activeFormSchema" :key="field" :config="schema" :value="dialogFormPayload[field]" :label="schema.label" :context="dialogFormPayload" @update="value => dialogFormPayload[field] = value" /></div>
            <template #footer><el-button @click="varDialogVisible = false">取消</el-button><el-button type="primary" @click="confirmSaveVar">保存变量</el-button></template>
        </el-dialog>
    </section>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Copy, MoreHorizontal, Pencil, Plus, Search, Trash2, X } from 'lucide-vue-next'
import { useIdeStore } from '@/stores'
import ParamRenderer from '@/components/ParamRenderer.vue'

const store=useIdeStore()
const activeTab=ref('user')
const query=ref('')
const varDialogVisible=ref(false)
const isEditing=ref(false)
const editingKey=ref('')
const dialogFormPayload=reactive({name:'',type:'string',value_number:0,value_string:'',value_bool:false,value_json:''})
const sourceLabels={user:'项目',ctx:'上下文',env:'系统'}
const systemEnvList=[
    {key:'current_time',desc:'系统当前时间戳（ms）'},
    {key:'project_path',desc:'当前自动化项目根目录'},
    {key:'last_error',desc:'最近一次节点的运行错误'},
    {key:'loop_index',desc:'当前循环索引'}
]
const ctxFieldList=[
    {field:'work_mode',label:'工作模式'}, {field:'title',label:'窗口标题'}, {field:'is_emulator',label:'模拟器模式'},
    {field:'content_offset',label:'内容偏移'}, {field:'target_content_size',label:'目标内容尺寸'}
]
const getCtxFieldValue=field=>{const ctx=store.currentContext||{}; if(field==='work_mode')return ctx.workMode||'window';if(field==='title')return ctx.windowTitle||'—';if(field==='is_emulator')return !!ctx.isEmulator;if(field==='content_offset')return Array.isArray(ctx.contentOffset)?ctx.contentOffset:[ctx.offsetTop||0,ctx.offsetBottom||0,ctx.offsetLeft||0,ctx.offsetRight||0];if(field==='target_content_size')return Array.isArray(ctx.targetSize)?ctx.targetSize:[ctx.targetWidth||0,ctx.targetHeight||0];return '—'}
const formatValue=value=>{if(value===undefined||value===null||value==='')return '—';if(typeof value==='boolean')return value?'True':'False';if(Array.isArray(value)||typeof value==='object')return JSON.stringify(value);return String(value)}
const typeInfo=value=>{if(typeof value==='boolean')return ['boolean','BOOL'];if(typeof value==='number')return ['number','NUM'];if(Array.isArray(value))return ['list','LIST'];if(value&&typeof value==='object')return ['dict','DICT'];return ['string','STR']}
const referenceCounts=computed(()=>{const counts={};const names=Object.keys(store.blueprint?.variables||{});const scan=value=>{if(typeof value==='string')names.forEach(name=>{if(value===name||value.includes(`$var{${name}}`)||value.includes(`$var.${name}`))counts[name]=(counts[name]||0)+1});else if(value&&typeof value==='object')Object.values(value).forEach(scan)};const graphs=[store.blueprint?.main_graph,...(store.blueprint?.functions||[]).map(item=>item.graph),store.blueprint?.page_map];graphs.forEach(graph=>(graph?.nodes||[]).forEach(node=>scan(node.params)));return counts})
const userVarList=computed(()=>Object.entries(store.blueprint?.variables||{}).map(([key,value])=>{const [type,typeLabel]=typeInfo(value);return{key,value,type,typeLabel,displayValue:formatValue(value),refCount:referenceCounts.value[key]||0}}))
const unusedVarCount=computed(()=>userVarList.value.filter(item=>item.refCount===0).length)
const userRows=computed(()=>userVarList.value.map(item=>({kind:'user',key:item.key,expression:`$var{${item.key}}`,value:item.displayValue,description:item.refCount?`${item.refCount} 次引用`:'未引用',type:item.typeLabel,source:item})))
const ctxRows=computed(()=>ctxFieldList.map(item=>({kind:'ctx',key:item.field,expression:`$ctx{${item.field}}`,value:formatValue(getCtxFieldValue(item.field)),description:item.label,type:''})))
const envRows=computed(()=>systemEnvList.map(item=>({kind:'env',key:item.key,expression:`$env{${item.key}}`,value:'运行时提供',description:item.desc,type:''})))
const allRows=computed(()=>[...userRows.value,...ctxRows.value,...envRows.value])
const tabs=computed(()=>[{id:'user',label:'用户变量',count:userRows.value.length},{id:'ctx',label:'运行上下文',count:ctxRows.value.length},{id:'env',label:'系统变量',count:envRows.value.length}])
const visibleRows=computed(()=>{const needle=query.value.trim().toLowerCase();const base=needle?allRows.value:({user:userRows.value,ctx:ctxRows.value,env:envRows.value}[activeTab.value]||[]);return needle?base.filter(row=>[row.expression,row.value,row.description,sourceLabels[row.kind]].join(' ').toLowerCase().includes(needle)):base})
const emptyLabel=computed(()=>activeTab.value==='user'?'还没有用户变量':'没有可用变量')
const emptyHint=computed(()=>activeTab.value==='user'?'创建变量后可在节点参数中复用。':'运行上下文建立后会在这里显示。')
const activeFormSchema=computed(()=>({name:{type:'str',label:'变量名称',placeholder:'例如 run_count'},type:{type:'select',label:'数据类型',options:[{label:'数字',value:'number'},{label:'文本',value:'string'},{label:'布尔',value:'boolean'},{label:'数组',value:'list'},{label:'字典',value:'dict'}]},value_number:{type:'int',label:'初始数值',default:0,visible_if:{field:'type',operator:'eq',value:'number'}},value_string:{type:'str',label:'初始文本',default:'',placeholder:'输入初始字符串',visible_if:{field:'type',operator:'eq',value:'string'}},value_bool:{type:'bool',label:'初始状态',default:false,visible_if:{field:'type',operator:'eq',value:'boolean'}},value_json:{type:'textarea',label:'初始 JSON',default:'',placeholder:'数组如 ["a"]；字典如 {"key":"value"}',rows:4,visible_if:{field:'type',operator:'in',value:['list','dict']}}}))
const resetDraft=()=>Object.assign(dialogFormPayload,{name:'',type:'string',value_number:0,value_string:'',value_bool:false,value_json:''})
const openCreateDialog=()=>{isEditing.value=false;editingKey.value='';resetDraft();varDialogVisible.value=true}
const openEditDialog=item=>{isEditing.value=true;editingKey.value=item.key;resetDraft();dialogFormPayload.name=item.key;dialogFormPayload.type=item.type;if(item.type==='number')dialogFormPayload.value_number=Number(item.value)||0;else if(item.type==='string')dialogFormPayload.value_string=String(item.value??'');else if(item.type==='boolean')dialogFormPayload.value_bool=Boolean(item.value);else dialogFormPayload.value_json=JSON.stringify(item.value??(item.type==='list'?[]:{}),null,2);varDialogVisible.value=true}
const confirmSaveVar=async()=>{const name=String(dialogFormPayload.name||'').trim();if(!/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(name))return ElMessage.warning('名称需以字母或下划线开头，只能包含字母、数字和下划线');if(!isEditing.value&&store.blueprint?.variables?.[name]!==undefined)return ElMessage.warning('变量名称已存在');let value;if(dialogFormPayload.type==='number')value=Number(dialogFormPayload.value_number)||0;else if(dialogFormPayload.type==='string')value=String(dialogFormPayload.value_string??'');else if(dialogFormPayload.type==='boolean')value=Boolean(dialogFormPayload.value_bool);else{try{value=dialogFormPayload.value_json?JSON.parse(dialogFormPayload.value_json):(dialogFormPayload.type==='list'?[]:{})}catch{return ElMessage.error('JSON 格式无效')}}if(!store.blueprint.variables)store.blueprint.variables={};if(isEditing.value&&editingKey.value!==name)delete store.blueprint.variables[editingKey.value];store.blueprint.variables[name]=value;await store.saveProjectMeta();varDialogVisible.value=false;ElMessage.success('变量已保存')}
const copyExpression=async expression=>{try{await navigator.clipboard.writeText(expression);ElMessage.success(`已复制 ${expression}`)}catch{ElMessage.error('复制失败')}}
const handleDeleteVar=async name=>{try{await ElMessageBox.confirm(`删除变量“${name}”？现有引用将失效。`,'删除变量',{type:'warning'});delete store.blueprint.variables[name];await store.saveProjectMeta()}catch{}}
const handleClearUnused=async()=>{const names=userVarList.value.filter(item=>item.refCount===0).map(item=>item.key);if(!names.length)return;try{await ElMessageBox.confirm(`删除 ${names.length} 个未引用变量？`,'清理未引用变量',{type:'warning'});names.forEach(name=>delete store.blueprint.variables[name]);await store.saveProjectMeta();ElMessage.success('未引用变量已清理')}catch{}}
const handleToolbarCommand=command=>{if(command==='clear-unused')handleClearUnused()}
</script>

<style scoped>
.variables-panel{height:100%;display:flex;flex-direction:column;overflow:hidden;background:var(--app-bg-sidebar)}.variables-toolbar{height:42px;display:flex;align-items:center;gap:5px;padding:7px 8px;border-bottom:1px solid var(--app-separator)}.variable-search{min-width:0;flex:1;height:28px;display:flex;align-items:center;gap:6px;padding:0 7px;border:1px solid var(--app-border-default);border-radius:6px;background:var(--app-bg-input);color:var(--app-text-secondary)}.variable-search:focus-within{border-color:var(--app-color-primary);box-shadow:var(--focus-ring)}.variable-search input{min-width:0;flex:1;border:0;outline:0;background:transparent;color:var(--app-text-primary);font-size:11px}.variable-search button,.toolbar-button,.row-actions button{display:grid;place-items:center;padding:0;border:0;background:transparent;color:var(--app-text-secondary);cursor:pointer}.variable-search button{width:20px;height:20px}.toolbar-button{width:28px;height:28px;border-radius:6px}.toolbar-button:hover{background:var(--app-bg-hover);color:var(--app-text-primary)}.toolbar-button.primary{background:var(--app-color-primary);color:var(--app-color-on-primary)}.variable-tabs{height:36px;display:grid;grid-template-columns:repeat(3,1fr);padding:4px 7px;border-bottom:1px solid var(--app-separator)}.variable-tabs button{min-width:0;display:flex;align-items:center;justify-content:center;gap:5px;border:0;border-radius:5px;background:transparent;color:var(--app-text-secondary);font-size:10.5px;cursor:pointer}.variable-tabs button.active{background:var(--app-bg-raised);color:var(--app-text-primary)}.variable-tabs small{padding:0 4px;border-radius:8px;background:var(--app-bg-hover);font-size:10px}.search-summary{padding:8px 10px;border-bottom:1px solid var(--app-separator);color:var(--app-text-secondary);font-size:10.5px}.search-summary strong{color:var(--app-text-primary)}.variable-list{flex:1;overflow:auto;padding:5px}.variable-row{width:100%;min-height:54px;display:flex;flex-direction:column;gap:5px;position:relative;padding:8px;border:0;border-radius:6px;background:transparent;color:inherit;text-align:left;cursor:default}.variable-row:hover{background:var(--app-bg-hover)}.row-main{min-width:0;display:flex;align-items:center;gap:5px;padding-right:68px}.row-main code{min-width:0;overflow:hidden;color:var(--app-text-primary);font-size:11px;text-overflow:ellipsis;white-space:nowrap}.source-tag,.type-tag{flex:0 0 auto;padding:1px 4px;border-radius:4px;background:var(--app-bg-raised);color:var(--app-text-secondary);font-size:10px}.row-detail{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;color:var(--app-text-secondary);font-size:10px}.row-detail span,.row-detail small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.row-actions{display:none;position:absolute;top:7px;right:7px;align-items:center;gap:2px}.variable-row:hover .row-actions,.variable-row:focus-within .row-actions{display:flex}.row-actions button{width:22px;height:22px;border-radius:4px}.row-actions button:hover{background:var(--app-bg-raised);color:var(--app-text-primary)}.row-actions button.danger:hover{color:var(--app-color-danger)}.empty-state{height:100%;min-height:180px;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:6px;padding:20px;text-align:center}.empty-state strong{font-size:12px}.empty-state span{max-width:220px;color:var(--app-text-secondary);font-size:10.5px;line-height:1.5}.empty-state button{margin-top:4px;border:0;background:transparent;color:var(--app-color-primary);cursor:pointer}.dialog-heading{display:flex;align-items:center;gap:7px}.dialog-form-body{display:flex;flex-direction:column;gap:2px}
</style>
