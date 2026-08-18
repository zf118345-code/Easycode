// frontend/src/components/controls/index.js
// 统一控件库：所有文本输入（str / string / textarea / variable）统一走 VariableAwareInput
// （普通文本 + $var{} / $ctx{} / $env{} 变量高亮 chip，详见 VariableAwareInput.vue）
import VariableAwareInput from './VariableAwareInput.vue'
import ControlNumber from './ControlNumber.vue'
import ControlSelect from './ControlSelect.vue'
import ControlSwitch from './ControlSwitch.vue'
import ControlWindowSelect from './ControlWindowSelect.vue'
import ControlFileHover from './ControlFileHover.vue'
import ControlCoordPicker from './ControlCoordPicker.vue'
import ControlDict from './ControlDict.vue'
import ControlConditionList from './ControlConditionList.vue'
import Margin4Control from './Margin4Control.vue'
import Size2Control from './Size2Control.vue'
import ControlSlider from './ControlSlider.vue'         // 新
import ControlRadioGroup from './ControlRadioGroup.vue'   // 新增
import ControlPageSelect from './ControlPageSelect.vue'  // 新增：目标页面下拉（拓扑页面动态取数）
import ControlCaptureField from './ControlCaptureField.vue'  // 控件名称（只读 + 捕获/重置按钮）

export const controlMap = {
    str: VariableAwareInput,
    string: VariableAwareInput,
    textarea: VariableAwareInput,
    variable: VariableAwareInput,   // 彻底取消变量选择器分类：与普通输入框统一
    capture_str: ControlCaptureField,  // 控件名称：只读 + 捕获控件/重置控件按钮
    int: ControlNumber,
    float: ControlNumber,
    number: ControlNumber,
    slider: ControlSlider,
    bool: ControlSwitch,
    switch: ControlSwitch,
    select: ControlSelect,
    radio: ControlRadioGroup,
    window_select: ControlWindowSelect,
    page_select: ControlPageSelect,
    file: ControlFileHover,
    list_int: ControlCoordPicker,
    region: ControlCoordPicker,
    list_int2: ControlCoordPicker,
    list_int2_picker: ControlCoordPicker,
    list_int4: ControlCoordPicker,
    list_int4_picker: ControlCoordPicker,
    dict: ControlDict,
    condition_list_editor: ControlConditionList,
    branch_candidate_editor: ControlConditionList,
    margin4: Margin4Control,
    size2: Size2Control
}