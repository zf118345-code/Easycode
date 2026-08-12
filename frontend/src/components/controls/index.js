// frontend/src/components/controls/index.js
import ControlString from './ControlString.vue'
import ControlNumber from './ControlNumber.vue'
import ControlSelect from './ControlSelect.vue'
import ControlSwitch from './ControlSwitch.vue'
import ControlWindowSelect from './ControlWindowSelect.vue'
import ControlFileHover from './ControlFileHover.vue'
import ControlCoordPicker from './ControlCoordPicker.vue'
import ControlDict from './ControlDict.vue'
import ControlConditionList from './ControlConditionList.vue'
import VariableInputControl from './VariableInputControl.vue'
import Margin4Control from './Margin4Control.vue'
import Size2Control from './Size2Control.vue'
import ControlSlider from './ControlSlider.vue'         // 新
import ControlRadioGroup from './ControlRadioGroup.vue'   // 新增
import ControlTextarea from './ControlTextarea.vue'     // 新增

export const controlMap = {
    str: ControlString,
    string: ControlString,
    textarea: ControlTextarea,
    int: ControlNumber,
    float: ControlNumber,
    number: ControlNumber,
    slider: ControlSlider,
    bool: ControlSwitch,
    switch: ControlSwitch,
    select: ControlSelect,
    radio: ControlRadioGroup,
    window_select: ControlWindowSelect,
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
    size2: Size2Control,
    variable: VariableInputControl
}