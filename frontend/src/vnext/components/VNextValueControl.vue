<template>
    <div v-if="actionsOnly" class="value-actions-only">
        <button v-for="action in actions" :key="action.id" type="button" class="app-field-action" :disabled="disabled" :data-parameter-action-id="action.id" :title="actionLabel(action.id)" :aria-label="actionLabel(action.id)" @click="emit('action',action)"><component :is="actionIcon(action.id)" :size="14" aria-hidden="true" /></button>
    </div>

    <select v-else-if="controlType === 'select'" data-control-surface :aria-label="label" :aria-invalid="invalid ? 'true' : undefined" :aria-describedby="describedBy || undefined" :disabled="disabled" :value="String(modelValue ?? '')" :required="required" @change="updateChoice">
        <option v-if="mixed" value="" disabled>多个值</option>
        <option v-if="!required" value="">{{ ui.effective_default_label || '留空' }}</option>
        <option v-for="option in options" :key="String(option.value)" :value="String(option.value)" :disabled="option.disabled">{{ option.label }}</option>
    </select>

    <label v-else-if="controlType === 'toggle'" class="value-toggle">
        <input type="checkbox" :aria-label="label" :aria-invalid="invalid ? 'true' : undefined" :aria-describedby="describedBy || undefined" :disabled="disabled" :checked="Boolean(modelValue)" :indeterminate="mixed" @change="update(($event.target as HTMLInputElement).checked)" />
        <i aria-hidden="true" /><em>{{ mixed ? '多个值' : modelValue ? toggleLabels.trueLabel : toggleLabels.falseLabel }}</em>
    </label>

    <div v-else-if="controlType === 'slider-number'" class="value-slider">
        <input type="range" :aria-label="`${label}滑块`" :disabled="disabled" :min="minimum" :max="maximum" :step="numericStep" :value="displayNumber" @input="updateNumber" />
        <input type="number" data-control-surface :aria-label="`${label}数值`" :aria-invalid="invalid ? 'true' : undefined" :aria-describedby="describedBy || undefined" :disabled="disabled" :min="minimum" :max="maximum" :step="numericStep" :value="displayNumber" @change="updateNumber" />
        <span v-if="ui.unit || isPercent" class="app-control-adornment">{{ isPercent ? '%' : ui.unit }}</span>
    </div>

    <input v-else-if="controlType === 'number'" data-control-surface type="number" :aria-label="label" :aria-invalid="invalid ? 'true' : undefined" :aria-describedby="describedBy || undefined" :disabled="disabled" :min="minimum" :max="maximum" :step="numericStep" :value="displayNumber" :required="required" :placeholder="placeholder" @change="updateNumber" />

    <div v-else-if="controlType === 'color'" class="value-color" :class="{ 'is-empty': !hasColorValue }">
        <input class="color-swatch" type="color" :aria-label="`${label}颜色预览`" :disabled="disabled" :value="colorHex" @input="updateColorHex" />
        <input class="color-hex" data-control-surface type="text" :aria-label="`${label}十六进制颜色`" :aria-invalid="invalid ? 'true' : undefined" :aria-describedby="describedBy || undefined" :disabled="disabled" :value="colorText" pattern="#[0-9A-Fa-f]{3}|#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{8}" placeholder="#RRGGBB" @change="updateColorText" />
        <label class="color-alpha"><span>透明</span><input data-control-surface type="number" :aria-label="`${label}透明度`" :disabled="disabled" min="0" max="255" step="1" :value="hasColorValue ? colorValue.alpha : ''" placeholder="255" @change="updateColorAlpha" /></label>
        <button v-for="action in actions" :key="action.id" type="button" class="app-field-action" :disabled="disabled" :data-parameter-action-id="action.id" :title="actionLabel(action.id)" :aria-label="actionLabel(action.id)" @click="emit('action',action)"><component :is="actionIcon(action.id)" :size="14" aria-hidden="true" /></button>
    </div>

    <div v-else-if="controlType === 'duration'" class="value-duration">
        <input type="number" data-control-surface :aria-label="label" :aria-invalid="invalid ? 'true' : undefined" :aria-describedby="describedBy || undefined" :disabled="disabled" min="0" step="1" :value="durationAmount" :required="required" :placeholder="placeholder || '例如：500'" @change="updateDuration" />
        <select v-model="durationUnit" data-control-surface aria-label="时间单位" :disabled="disabled" @change="updateDurationUnit"><option value="ms">毫秒</option><option value="s">秒</option><option value="min">分钟</option></select>
    </div>

    <div v-else-if="controlType === 'coordinate' || controlType === 'region'" class="value-vector">
        <label v-for="(axisLabel,index) in vectorLabels" :key="axisLabel"><span>{{ axisLabel }}</span><input type="number" data-control-surface :disabled="disabled" min="0" :value="vectorValue[index] ?? 0" @change="updateVector(index,$event)" /></label>
        <button v-for="action in actions" :key="action.id" type="button" class="app-field-action" :disabled="disabled" :data-parameter-action-id="action.id" :title="actionLabel(action.id)" :aria-label="actionLabel(action.id)" @click="emit('action',action)"><component :is="actionIcon(action.id)" :size="14" aria-hidden="true" /></button>
    </div>

    <div v-else-if="controlType === 'resource'" class="value-resource">
        <select data-control-surface :aria-label="label" :aria-invalid="invalid ? 'true' : undefined" :aria-describedby="describedBy || undefined" :disabled="disabled" :value="assetValue" :required="required" @change="update(($event.target as HTMLSelectElement).value)">
            <option value="">选择图片资源</option>
            <option v-if="assetValue && !currentAsset" :value="assetValue">{{ missingAssetLabel }}</option>
            <option v-for="asset in assets" :key="asset.asset_id" :value="asset.asset_id">{{ asset.display_name }}</option>
        </select>
        <button v-for="action in actions" :key="action.id" type="button" class="app-field-action" :disabled="disabled" :data-parameter-action-id="action.id" :title="actionLabel(action.id)" :aria-label="actionLabel(action.id)" @click="emit('action',action)"><component :is="actionIcon(action.id)" :size="14" aria-hidden="true" /></button>
    </div>

    <div v-else-if="controlType === 'file' || controlType === 'directory'" class="value-reference">
        <div :class="['reference-summary', { empty: !referenceValue }]" data-control-surface :data-disabled="disabled ? 'true' : undefined" :aria-label="label" :aria-describedby="describedBy || undefined">
            <component :is="controlType === 'directory' ? Folder : File" :size="15" aria-hidden="true" />
            <span><strong>{{ referenceLabel }}</strong><small v-if="referenceAccess">{{ referenceAccess }}</small></span>
        </div>
        <button v-for="action in actions" :key="action.id" type="button" class="app-field-action" :disabled="disabled" :data-parameter-action-id="action.id" :title="actionLabel(action.id)" :aria-label="actionLabel(action.id)" @click="emit('action',action)"><component :is="actionIcon(action.id)" :size="14" aria-hidden="true" /></button>
    </div>

    <div v-else-if="controlType === 'control-selector' || controlType === 'gesture-path'" class="value-reference">
        <div :class="['reference-summary', { empty: !capturedReferencePresent }]" data-control-surface :data-disabled="disabled ? 'true' : undefined" :aria-label="label" :aria-describedby="describedBy || undefined">
            <component :is="controlType === 'control-selector' ? (isWindowBinding ? AppWindow : MousePointer2) : Route" :size="15" aria-hidden="true" />
            <span><strong>{{ capturedReferenceLabel }}</strong><small v-if="capturedReferenceDetail">{{ capturedReferenceDetail }}</small></span>
        </div>
        <button v-for="action in actions" :key="action.id" type="button" class="app-field-action" :disabled="disabled" :data-parameter-action-id="action.id" :title="actionLabel(action.id)" :aria-label="actionLabel(action.id)" @click="emit('action',action)"><component :is="actionIcon(action.id)" :size="14" aria-hidden="true" /></button>
    </div>

    <div v-else-if="isBooleanMap" class="value-boolean-map" role="group" :aria-label="label">
        <label
            v-for="entry in booleanMapEntries"
            :key="entry.key"
            :class="{ 'is-fixed': entry.fixed }"
            :title="entry.fixed ? entry.reason : undefined"
            :data-fixed-value="entry.fixed ? String(entry.enabled) : undefined"
        >
            <input
                type="checkbox"
                :aria-label="entry.ariaLabel"
                :disabled="disabled || entry.fixed"
                :checked="entry.enabled"
                @change="updateBooleanMapEntry(entry.key, ($event.target as HTMLInputElement).checked)"
            />
            <span>{{ entry.key }}</span>
            <span v-if="entry.fixed" class="boolean-map-fixed-state"><LockKeyhole :size="12" aria-hidden="true" />{{ entry.enabled ? '必选' : '不可选' }}</span>
        </label>
        <span v-if="!booleanMapEntries.length" class="value-boolean-map-empty">暂无可选项</span>
    </div>

    <div v-else-if="isStructured" class="value-structured">
        <textarea data-control-surface :aria-label="label" :aria-invalid="invalid ? 'true' : undefined" :aria-describedby="describedBy || undefined" :disabled="disabled" :value="structuredValue" :placeholder="placeholder" spellcheck="false" @change="updateStructured" />
        <button v-for="action in actions" :key="action.id" type="button" class="app-field-action" :disabled="disabled" :data-parameter-action-id="action.id" :title="actionLabel(action.id)" :aria-label="actionLabel(action.id)" @click="emit('action',action)"><component :is="actionIcon(action.id)" :size="14" aria-hidden="true" /></button>
    </div>

    <input v-else data-control-surface :type="controlType === 'time' ? temporalInputType : 'text'" :aria-label="label" :aria-invalid="invalid ? 'true' : undefined" :aria-describedby="describedBy || undefined" :disabled="disabled" :step="controlType === 'time' && temporalInputType !== 'date' ? 1 : undefined" :value="controlType === 'time' ? temporalStringValue : stringValue" :placeholder="placeholder" :required="required" @change="update(($event.target as HTMLInputElement).value)" @keydown.enter="($event.target as HTMLInputElement).blur()" />
</template>

<script setup lang="ts">
import { computed, markRaw, ref, watch } from 'vue'
import { AppWindow, Camera, Crosshair, File, Folder, FolderOpen, LockKeyhole, MousePointer2, Pipette, Route, Save, ScanLine } from 'lucide-vue-next'
import type { AssetDefinition, ParameterControlType, ParameterDefinition, ParameterUiAction, ParameterUiContract, PlayerControlOption } from '../types'
import { COLOR_FIELD_IDS, formatRgbaHex, normalizeRgbaColor, parseRgbaHex } from '../colorValue'

type Constraints = NonNullable<ParameterDefinition['constraints']>
const props=withDefaults(defineProps<{
    controlType:ParameterControlType;modelValue:unknown;required?:boolean;options?:Array<(PlayerControlOption&{disabled?:boolean})>;
    constraints?:Constraints;ui?:ParameterUiContract;assets?:AssetDefinition[];actions?:ParameterUiAction[];placeholder?:string;valueType?:string;
    toggleLabels?:{trueLabel:string;falseLabel:string};actionsOnly?:boolean;label?:string;disabled?:boolean;invalid?:boolean;describedBy?:string;mixed?:boolean
}>(),{required:false,options:()=>[],constraints:()=>({}),ui:()=>({control:'expression',actions:[]}),assets:()=>[],actions:()=>[],placeholder:'',valueType:'string',toggleLabels:()=>({trueLabel:'开启',falseLabel:'关闭'}),actionsOnly:false,label:'值',disabled:false,invalid:false,describedBy:'',mixed:false})
const emit=defineEmits<{'update:modelValue':[value:unknown];action:[action:ParameterUiAction]}>()
const isPercent=computed(()=>props.ui.display==='percent')
const minimum=computed(()=>Number(props.constraints.min??props.constraints.minimum??(props.controlType==='slider-number'?0:-999999999))*(isPercent.value?100:1))
const maximum=computed(()=>Number(props.constraints.max??props.constraints.maximum??(props.controlType==='slider-number'?100:999999999))*(isPercent.value?100:1))
const numericStep=computed(()=>Number(props.constraints.step??1)*(isPercent.value?100:1))
const displayNumber=computed(()=>props.modelValue==null||props.modelValue===''?'':Number(props.modelValue)*(isPercent.value?100:1))
const clampColor=(value:unknown,fallback=0)=>{const number=Number(value);return Number.isFinite(number)?Math.max(0,Math.min(255,Math.round(number))):fallback}
const colorValue=computed(()=>normalizeRgbaColor(props.modelValue))
const hasColorValue=computed(()=>{if(!props.modelValue||typeof props.modelValue!=='object'||Array.isArray(props.modelValue))return false;const value=props.modelValue as Record<string,unknown>;return ['red','green','blue','alpha','color.field.red','color.field.green','color.field.blue','color.field.alpha'].some(key=>value[key]!==undefined)})
const colorHex=computed(()=>formatRgbaHex(colorValue.value))
// Alpha has its own visible field. Keep the primary text stable as #RRGGBB;
// pasting #RRGGBBAA is still accepted and updates both controls atomically.
const colorText=computed(()=>hasColorValue.value?formatRgbaHex(colorValue.value):'')
const vectorLabels=computed(()=>props.controlType==='coordinate'?['X','Y']:['X','Y','宽','高'])
const vectorValue=computed(()=>{if(Array.isArray(props.modelValue))return props.modelValue.map(value=>Number(value)||0);if(props.modelValue&&typeof props.modelValue==='object'){const value=props.modelValue as Record<string,unknown>;return props.controlType==='coordinate'?[Number(value.x)||0,Number(value.y)||0]:[Number(value.x)||0,Number(value.y)||0,Number(value.width)||0,Number(value.height)||0]}return []})
const assetValue=computed(()=>props.modelValue&&typeof props.modelValue==='object'?String((props.modelValue as {asset_id?:unknown}).asset_id||''):String(props.modelValue||''))
const currentAsset=computed(()=>props.assets.find(asset=>asset.asset_id===assetValue.value))
const missingAssetLabel=computed(()=>`已选择图片 · ${assetValue.value.replace(/^profile_/,'').slice(0,8)}`)
const referenceValue=computed<Record<string,unknown>|null>(()=>{
    if(props.modelValue&&typeof props.modelValue==='object')return props.modelValue as Record<string,unknown>
    const referenceId=String(props.modelValue||'').trim()
    return referenceId?{reference_id:referenceId,display_name:referenceId}:null
})
const referenceLabel=computed(()=>String(referenceValue.value?.display_name||referenceValue.value?.name||referenceValue.value?.reference_id||(props.controlType==='directory'?'尚未选择文件夹':'尚未选择文件')))
const referenceAccess=computed(()=>{const access=referenceValue.value?.access;return Array.isArray(access)?access.map(item=>String(item)).join(' · '):''})
const isStructured=computed(()=>['list','key-value','json','instance-multi-select'].includes(props.controlType))
const normalizedValueType=computed(()=>{let value=props.valueType.trim();while(value.startsWith('optional<')&&value.endsWith('>'))value=value.slice(9,-1);return value})
const isWindowBinding=computed(()=>normalizedValueType.value==='window_binding')
const capturedReferencePresent=computed(()=>props.controlType==='gesture-path'?Array.isArray(props.modelValue)&&props.modelValue.length>0:Boolean(props.modelValue&&typeof props.modelValue==='object'))
const capturedReferenceLabel=computed(()=>{if(props.controlType==='gesture-path')return capturedReferencePresent.value?`已记录 ${(props.modelValue as unknown[]).length} 个路径点`:'尚未绘制路径';if(!capturedReferencePresent.value)return isWindowBinding.value?'尚未捕获窗口':'尚未捕获控件';const value=props.modelValue as Record<string,unknown>;if(isWindowBinding.value)return String(value.title||'已捕获窗口');const info=value.info&&typeof value.info==='object'?value.info as Record<string,unknown>:{};return String(value['control_selector.field.name']||info.name||info.title||value.display_name||'已捕获控件')})
const capturedReferenceDetail=computed(()=>{
    if(props.controlType==='gesture-path'||!capturedReferencePresent.value)return ''
    const value=props.modelValue as Record<string,unknown>
    if(isWindowBinding.value)return [value.executable_name,value.class_name].map(item=>String(item||'').trim()).filter(Boolean).join(' · ')||'已保存稳定窗口身份'
    const strategies=value['control_selector.field.strategies']
    if(Array.isArray(strategies)&&strategies.length){
        const statuses=strategies.map(item=>item&&typeof item==='object'?String(((item as Record<string,unknown>).last_test as Record<string,unknown>|undefined)?.status||'not_tested'):'not_tested')
        const summary=statuses.includes('ambiguous')?'需要重新捕获':statuses.includes('success')?'已验证':statuses.every(status=>status==='not_found')?'当前未找到':'等待验证'
        return `${strategies.length} 条定位策略 · ${summary}`
    }
    const info=value.info&&typeof value.info==='object'?value.info as Record<string,unknown>:{}
    return String(value['control_selector.field.resource_id']||value['control_selector.field.automation_id']||value['control_selector.field.content_description']||value['control_selector.field.control_type']||value['control_selector.field.class_name']||info.control_type||info.class_name||'已保存稳定选择器')
})
const structuredValue=computed(()=>typeof props.modelValue==='string'?props.modelValue:props.modelValue==null?'':JSON.stringify(props.modelValue,null,2))
const stringValue=computed(()=>props.modelValue==null?'':String(props.modelValue))
const isBooleanMap=computed(()=>props.controlType==='key-value'&&normalizedValueType.value==='map<string,bool>'&&props.modelValue!==null&&typeof props.modelValue==='object'&&!Array.isArray(props.modelValue))
const booleanMapEntries=computed(()=>{
    if(!isBooleanMap.value)return []
    const values=props.modelValue as Record<string,unknown>
    const preferred=props.options.map(option=>String(option.value)).filter(key=>Object.prototype.hasOwnProperty.call(values,key))
    const remaining=Object.keys(values).filter(key=>!preferred.includes(key))
    return [...preferred,...remaining].map(key=>{
        const option=props.options.find(item=>String(item.value)===key)
        const fixed=typeof option?.fixed_value==='boolean'
        const enabled=fixed?Boolean(option?.fixed_value):Boolean(values[key])
        const reason=option?.fixed_reason||`此选项由开发者固定为${enabled?'必选':'不可选'}`
        return {key,enabled,fixed,reason,ariaLabel:fixed?`${key}，${enabled?'固定必选':'固定不可选'}，${reason}`:key}
    })
})
const temporalInputType=computed<'date'|'datetime-local'|'time'>(()=>normalizedValueType.value==='date'?'date':normalizedValueType.value==='datetime'?'datetime-local':'time')
const temporalStringValue=computed(()=>{const value=stringValue.value;if(temporalInputType.value==='date')return value.slice(0,10);if(temporalInputType.value==='datetime-local')return value.replace(/Z$/,'').slice(0,19);return value})
function durationMilliseconds(value:unknown){if(typeof value==='number')return Math.max(0,value);if(value&&typeof value==='object'&&'milliseconds'in value)return Math.max(0,Number((value as {milliseconds:unknown}).milliseconds)||0);const text=String(value||'').trim();const match=text.match(/^(\d+(?:\.\d+)?)\s*(毫秒|ms|秒|s|分钟|min)?$/i);if(!match)return 0;const amount=Number(match[1]);return amount*(match[2]==='秒'||match[2]?.toLowerCase()==='s'?1000:match[2]==='分钟'||match[2]?.toLowerCase()==='min'?60000:1)}
function bestDurationUnit(ms:number):'ms'|'s'|'min'{return ms>=60000&&ms%60000===0?'min':ms>=1000&&ms%1000===0?'s':'ms'}
const durationUnit=ref<'ms'|'s'|'min'>(bestDurationUnit(durationMilliseconds(props.modelValue)))
const durationAmount=computed(()=>{if(props.modelValue==null||props.modelValue==='')return '';const ms=durationMilliseconds(props.modelValue);return durationUnit.value==='min'?ms/60000:durationUnit.value==='s'?ms/1000:ms})
watch(()=>props.modelValue,value=>{if(props.controlType==='duration')durationUnit.value=bestDurationUnit(durationMilliseconds(value))})
function update(value:unknown){emit('update:modelValue',value)}
function updateChoice(event:Event){const selected=(event.target as HTMLSelectElement).value;update(props.options.find(option=>String(option.value)===selected)?.value??selected)}
function updateNumber(event:Event){const raw=(event.target as HTMLInputElement).value;if(raw===''){update(null);return}const value=Number(raw);update(isPercent.value?value/100:value)}
function colorFromHex(raw:string){return parseRgbaHex(raw,colorValue.value.alpha)}
function updateColor(value:ReturnType<typeof normalizeRgbaColor>){update({
    [COLOR_FIELD_IDS.red]:value.red,[COLOR_FIELD_IDS.green]:value.green,
    [COLOR_FIELD_IDS.blue]:value.blue,[COLOR_FIELD_IDS.alpha]:value.alpha,
})}
function updateColorHex(event:Event){const next=colorFromHex((event.target as HTMLInputElement).value);if(next)updateColor(next)}
function updateColorText(event:Event){const input=event.target as HTMLInputElement;const next=colorFromHex(input.value);if(next)updateColor(next);else input.value=colorHex.value}
function updateColorAlpha(event:Event){updateColor({...colorValue.value,alpha:clampColor((event.target as HTMLInputElement).value,255)})}
function updateVector(index:number,event:Event){const next=[...vectorValue.value];next[index]=Math.max(0,Number((event.target as HTMLInputElement).value)||0);update(props.controlType==='coordinate'?{x:next[0],y:next[1]}:{x:next[0],y:next[1],width:next[2],height:next[3]})}
function durationFactor(){return durationUnit.value==='min'?60000:durationUnit.value==='s'?1000:1}
function updateDuration(event:Event){const raw=(event.target as HTMLInputElement).value;if(raw===''){update(null);return}update({milliseconds:Math.round(Math.max(0,Number(raw))*durationFactor())})}
function updateDurationUnit(){if(durationAmount.value==='')return;update({milliseconds:Math.round(Math.max(0,Number(durationAmount.value))*durationFactor())})}
function updateStructured(event:Event){const text=(event.target as HTMLTextAreaElement).value.trim();if(props.controlType==='expression'){update(text);return}if(!text){update(null);return}try{update(JSON.parse(text))}catch{update(text)}}
function updateBooleanMapEntry(key:string,enabled:boolean){const option=props.options.find(item=>String(item.value)===key);if(typeof option?.fixed_value==='boolean')return;const next={...props.modelValue as Record<string,unknown>,[key]:enabled};props.options.forEach(item=>{if(typeof item.fixed_value==='boolean')next[String(item.value)]=item.fixed_value});update(next)}
function actionLabel(id:string){return ({'choose-resource':'选择资源','capture-image':'截图录入','pick-point':'取点','pick-region':'框选范围','pick-color':'从目标画面取色','capture-control':'捕获控件','capture-window':'捕获窗口','capture-path':'捕获路径','choose-file-read':'选择读取文件','choose-file-save':'选择保存位置','choose-directory':'选择文件夹'} as Record<string,string>)[id]||id}
function actionIcon(id:string){return markRaw(({'choose-resource':FolderOpen,'capture-image':Camera,'pick-point':Crosshair,'pick-region':ScanLine,'pick-color':Pipette,'capture-control':MousePointer2,'capture-window':AppWindow,'capture-path':Route,'choose-file-read':File,'choose-file-save':Save,'choose-directory':Folder} as Record<string,typeof Camera>)[id]||Crosshair)}
</script>

<style scoped>
input,select,textarea{width:100%;min-width:0;height:var(--app-control-default);padding:0 9px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);outline:0;background:var(--app-bg-input);color:var(--app-text-primary);font-family:var(--app-font-sans);font-size:var(--app-font-caption)}textarea{height:76px;padding:8px;resize:vertical;line-height:15px}.value-structured textarea,input[type=number],input[type=date],input[type=datetime-local],input[type=time]{font-family:var(--app-font-mono);font-variant-numeric:tabular-nums}input:hover:not(:disabled),select:hover:not(:disabled),textarea:hover:not(:disabled){border-color:var(--app-border-strong)}input:focus,select:focus,textarea:focus{border-color:var(--app-color-primary);box-shadow:var(--focus-ring)}input:disabled,select:disabled,textarea:disabled{opacity:.62;cursor:not-allowed}input[aria-invalid='true'],select[aria-invalid='true'],textarea[aria-invalid='true']{border-color:var(--app-color-danger)}input::placeholder,textarea::placeholder{color:var(--app-text-placeholder)}.value-toggle{position:relative;display:flex;align-items:center;gap:8px;width:max-content;max-width:100%;height:var(--app-control-default);cursor:pointer}.value-toggle:has(input:disabled){opacity:.62;cursor:not-allowed}.value-toggle input{position:absolute;inset:4px auto auto 4px;width:1px;height:1px;margin:0;padding:0;border:0;opacity:0}.value-toggle i{width:32px;height:18px;position:relative;border-radius:9px;background:var(--app-border-strong);transition:background .16s ease}.value-toggle input:focus-visible+i{box-shadow:var(--focus-ring)}.value-toggle i::after{content:"";position:absolute;top:2px;left:2px;width:14px;height:14px;border-radius:50%;background:var(--app-color-on-primary);transition:transform .16s ease}.value-toggle input:checked+i{background:var(--app-color-primary)}.value-toggle input:checked+i::after{transform:translateX(14px)}.value-toggle em{color:var(--app-text-secondary);font-size:var(--app-font-caption);font-style:normal}.value-slider{display:grid;grid-template-columns:minmax(0,1fr) 74px auto;align-items:center;gap:7px}.value-slider input[type=range]{height:18px;padding:0;border:0;box-shadow:none}.value-slider>span{color:var(--app-text-secondary);font-size:var(--app-font-caption)}.value-duration{display:grid;grid-template-columns:minmax(0,1fr) 82px;gap:5px}.value-color{display:grid;grid-template-columns:34px minmax(86px,1fr) 92px auto;gap:5px}.value-color .color-swatch{width:34px;padding:3px;cursor:pointer}.value-color .color-hex{font-family:var(--app-font-mono);text-transform:uppercase}.color-alpha{display:grid;grid-template-columns:34px minmax(0,1fr)}.color-alpha span{display:grid;place-items:center;border:1px solid var(--app-border-default);border-right:0;border-radius:var(--app-radius-sm) 0 0 var(--app-radius-sm);background:var(--app-bg-raised);color:var(--app-text-secondary);font-size:var(--app-font-caption)}.color-alpha input{padding-inline:6px;border-radius:0 var(--app-radius-sm) var(--app-radius-sm) 0}.value-vector{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.value-vector label{display:grid;grid-template-columns:24px minmax(0,1fr)}.value-vector label span{display:grid;place-items:center;border:1px solid var(--app-border-default);border-right:0;border-radius:var(--app-radius-sm) 0 0 var(--app-radius-sm);background:var(--app-bg-raised);color:var(--app-text-secondary);font-size:var(--app-font-caption)}.value-vector label input{border-radius:0 var(--app-radius-sm) var(--app-radius-sm) 0}.value-structured,.value-reference{display:grid;min-width:0;grid-template-columns:minmax(0,1fr) auto;align-items:start;gap:var(--app-spacing-xs)}.value-actions-only{display:flex;align-items:flex-start;gap:var(--app-spacing-xs)}.reference-summary{box-sizing:border-box;min-width:0;height:var(--app-control-default);display:flex;align-items:center;gap:7px;overflow:hidden;padding:0 9px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);background:var(--app-bg-input);color:var(--app-text-secondary)}.reference-summary>span{min-width:0;display:flex;flex:1;align-items:center;gap:7px;overflow:hidden}.reference-summary strong{overflow:hidden;color:var(--app-text-primary);font-family:var(--app-font-sans);font-size:var(--app-font-caption);font-weight:500;text-overflow:ellipsis;white-space:nowrap}.reference-summary small{overflow:hidden;font-size:var(--app-font-caption);text-overflow:ellipsis;white-space:nowrap}.reference-summary.empty strong{color:var(--app-text-placeholder);font-weight:400}
.reference-summary > svg { flex: none; }
.reference-summary strong,
.reference-summary small {
    overflow: hidden;
    line-height: 1;
    text-overflow: ellipsis;
    white-space: nowrap;
}
.reference-summary strong { min-width: 0; flex: 1; }
.reference-summary small { max-width: 42%; flex: none; color: var(--app-text-placeholder); }
.value-resource {
    display: flex;
    min-width: 0;
    align-items: flex-start;
    gap: var(--app-spacing-xs);
}
.value-resource > select { min-width: 0; flex: 1; }
.value-boolean-map{display:grid;gap:6px;padding:7px 9px;border:1px solid var(--app-border-default);border-radius:var(--app-radius-sm);background:var(--app-bg-input)}
.value-boolean-map label{display:flex;min-height:24px;align-items:center;gap:8px;color:var(--app-text-primary);font-size:var(--app-font-caption);cursor:pointer}
.value-boolean-map label:has(input:disabled){cursor:not-allowed}
.value-boolean-map label:has(input:disabled):not(.is-fixed){opacity:.62}
.value-boolean-map label.is-fixed>span:not(.boolean-map-fixed-state){color:var(--app-text-secondary)}
.value-boolean-map input{width:15px;height:15px;min-width:15px;margin:0;padding:0;accent-color:var(--app-color-primary)}
.boolean-map-fixed-state{display:inline-flex;align-items:center;gap:4px;margin-left:auto;color:var(--app-text-muted);font-size:var(--app-font-caption);white-space:nowrap}
.value-boolean-map-empty{color:var(--app-text-placeholder);font-size:var(--app-font-caption)}
</style>
