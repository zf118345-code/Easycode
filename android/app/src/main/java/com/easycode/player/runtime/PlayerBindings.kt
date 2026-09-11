package com.easycode.player.runtime

import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.profile.PlayerProfile
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import com.google.gson.JsonPrimitive

/** Applies the signed schema-3 Player form to a detached ECIR document.
 *
 * Labels never participate in execution.  Every write is resolved through the
 * stable binding ids carried by the signed form, mirroring the desktop
 * `apply_player_bindings` boundary.
 */
object PlayerBindings {
    fun bind(bundle: VerifiedBundle, profile: PlayerProfile, actionControlId: String = ""): BoundRun {
        val ecir = bundle.ecir.deepCopy()
        val controls = controls(bundle.form)
        val unknownValues = profile.values.keySet() - controls.keys
        if (unknownValues.isNotEmpty()) {
            fail("AND-BIND-001", "配置方案包含未发布控件：${unknownValues.sorted().first()}")
        }
        val functions = ecir.array("functions").mapNotNull {
            it.takeIf(JsonElement::isJsonObject)?.asJsonObject
        }.associateBy { it.string("function_id") }
        var entryFunctionId = ecir.string("entry_function_id")
        if (actionControlId.isNotBlank()) {
            val action = controls[actionControlId]
                ?: fail("AND-BIND-002", "Player 请求了未发布的函数按钮")
            if (action.string("type") != "button" || action.obj("binding").string("kind") != "function_action") {
                fail("AND-BIND-002", "Player 请求的控件不是函数按钮")
            }
            entryFunctionId = action.obj("binding").string("function_id")
        }
        if (entryFunctionId !in functions) fail("AND-BIND-003", "Player 入口函数未进入链接闭包：$entryFunctionId")

        val effective = JsonObject()
        for ((controlId, control) in controls) {
            if (control.string("type") != "button" && control.has("default")) {
                effective.add(controlId, control.get("default").deepCopy())
            }
        }
        for ((key, value) in profile.values.entrySet()) effective.add(key, value.deepCopy())

        val selectedTarget = selectTarget(bundle, profile.targetId)
        for ((controlId, control) in controls) {
            if (control.string("type") == "button") continue
            val binding = control.obj("binding")
            val relevant = when (binding.string("kind")) {
                "function_parameter" -> binding.string("function_id") == entryFunctionId
                "setting" -> binding.string("target_id") == profile.targetId
                else -> true
            }
            if (relevant && (control.bool("required") || sourceParameterRequired(functions, binding))) {
                if (!effective.has(controlId) || effective.get(controlId).isJsonNull) {
                    fail("AND-BIND-004", "Player 必填控件尚未填写：$controlId")
                }
            }
        }

        val instructions = collectInstructions(ecir)
        val slots = ecir.array("value_override_slots").mapNotNull { raw ->
            raw.takeIf(JsonElement::isJsonObject)?.asJsonObject
        }.associateBy { it.string("value_id") }
        val functionArguments = ecir.obj("function_arguments").deepCopy()
        val variableOverrides = ecir.obj("project_variable_overrides").deepCopy()
        val targetOverrides = ecir.obj("target_overrides").deepCopy()

        for ((controlId, value) in effective.entrySet()) {
            val control = controls[controlId]
                ?: fail("AND-BIND-001", "配置方案包含未发布控件：$controlId")
            if (control.string("type") == "button") fail("AND-BIND-005", "函数按钮不能保存字段值：$controlId")
            val sourceType = control.string("source_type")
            validateValue(value, sourceType, control.obj("constraints"), controlId)
            val binding = control.obj("binding")
            when (binding.string("kind")) {
                "project_variable" -> variableOverrides.add(binding.string("variable_id"), value.deepCopy())
                "function_parameter" -> {
                    val functionId = binding.string("function_id")
                    val arguments = functionArguments.get(functionId)
                        ?.takeIf(JsonElement::isJsonObject)?.asJsonObject ?: JsonObject().also {
                        functionArguments.add(functionId, it)
                    }
                    arguments.add(binding.string("parameter_id"), value.deepCopy())
                }
                "statement_parameter" -> {
                    val instructionId = binding.string("statement_id")
                    val instruction = instructions[instructionId]
                        ?: fail("AND-BIND-006", "语句绑定已失效：$instructionId")
                    val parameterId = binding.string("parameter_id")
                    if (instruction.obj("parameter_ids").string(parameterId) != parameterId) {
                        fail("AND-BIND-006", "语句参数稳定 ID 已失效：$instructionId/$parameterId")
                    }
                    val valueId = binding.string("value_id")
                    if (valueId.isBlank()) {
                        instruction.obj("arguments").add(parameterId, value.deepCopy())
                    } else {
                        val slot = slots[valueId]
                            ?: fail("AND-BIND-007", "嵌套值签名插槽已失效：$valueId")
                        if (
                            slot.string("function_id") != binding.string("function_id") ||
                            slot.string("statement_id") != instructionId ||
                            slot.string("parameter_id") != parameterId
                        ) fail("AND-BIND-007", "嵌套值签名插槽身份不一致：$valueId")
                        replaceAtPath(
                            instruction.obj("arguments").get(parameterId)
                                ?: fail("AND-BIND-007", "嵌套值签名根不存在：$valueId"),
                            slot.array("path"),
                            value,
                        )
                    }
                }
                "setting" -> {
                    // Android local currently has no unsigned target settings.
                    // Preserve a signed setting value for a future concrete
                    // consumer, but never silently reinterpret it.
                    val targetId = binding.string("target_id")
                    val settings = targetOverrides.get(targetId)
                        ?.takeIf(JsonElement::isJsonObject)?.asJsonObject ?: JsonObject().also {
                        targetOverrides.add(targetId, it)
                    }
                    settings.add(binding.string("setting_id"), value.deepCopy())
                }
                else -> fail("AND-BIND-008", "Android Player 不支持绑定类型：${binding.string("kind")}")
            }
        }
        if (targetOverrides.size() > 0) {
            fail("AND-BIND-009", "Android 本机目标没有已签名的可覆盖运行设置")
        }
        ecir.addProperty("entry_function_id", entryFunctionId)
        ecir.add("function_arguments", functionArguments)
        ecir.add("project_variable_overrides", variableOverrides)
        ecir.add("target_overrides", targetOverrides)
        return BoundRun(ecir, entryFunctionId, selectedTarget)
    }

    fun controls(form: JsonObject): Map<String, JsonObject> = buildMap {
        for (page in form.array("pages")) {
            if (!page.isJsonObject) continue
            for (raw in page.asJsonObject.array("controls")) {
                if (!raw.isJsonObject) continue
                val control = raw.asJsonObject
                val id = control.string("control_id")
                if (id.isBlank() || put(id, control) != null) fail("AND-BIND-010", "Player 控件 ID 缺失或重复")
            }
        }
    }

    private fun selectTarget(bundle: VerifiedBundle, requested: String): String {
        val targets = bundle.project.array("targets").mapNotNull {
            it.takeIf(JsonElement::isJsonObject)?.asJsonObject
        }
        if (targets.isEmpty()) {
            if (requested.isNotBlank()) fail("AND-TARGET-005", "无目标任务不能绑定目标：$requested")
            return ""
        }
        val selected = targets.firstOrNull { it.string("target_id") == requested }
            ?: fail("AND-TARGET-005", "配置方案目标不在签名闭包中：$requested")
        if (selected.string("type") != "android_local") fail("AND-TARGET-006", "APK 只能绑定 Android 本机目标")
        return requested
    }

    private fun sourceParameterRequired(
        functions: Map<String, JsonObject>,
        binding: JsonObject,
    ): Boolean {
        if (binding.string("kind") != "function_parameter") return false
        val function = functions[binding.string("function_id")] ?: return false
        val parameterId = binding.string("parameter_id")
        return function.array("parameter_definitions").any {
            it.isJsonObject && it.asJsonObject.string("parameter_id") == parameterId &&
                it.asJsonObject.bool("required", true)
        }
    }

    private fun collectInstructions(ecir: JsonObject): Map<String, JsonObject> {
        val result = linkedMapOf<String, JsonObject>()
        fun visit(value: JsonElement) {
            if (value.isJsonArray) value.asJsonArray.forEach(::visit)
            if (!value.isJsonObject) return
            val obj = value.asJsonObject
            val id = obj.string("instruction_id")
            if (id.isNotBlank() && obj.string("opcode").isNotBlank()) {
                if (result.put(id, obj) != null) fail("AND-BIND-006", "ECIR 包含重复语句 ID：$id")
            }
            obj.entrySet().forEach { visit(it.value) }
        }
        visit(ecir.array("functions"))
        return result
    }

    private fun replaceAtPath(root: JsonElement, path: JsonArray, replacement: JsonElement) {
        if (path.size() == 0 || path.size() > 64) fail("AND-BIND-007", "嵌套值签名路径无效")
        var current = root
        for (index in 0 until path.size() - 1) current = pathChild(current, path[index])
        val last = path[path.size() - 1]
        if (last.isJsonPrimitive && last.asJsonPrimitive.isNumber) {
            if (!current.isJsonArray) fail("AND-BIND-007", "嵌套值签名数组路径无效")
            val position = last.asInt
            if (position !in 0 until current.asJsonArray.size()) fail("AND-BIND-007", "嵌套值签名数组越界")
            current.asJsonArray.set(position, replacement.deepCopy())
        } else {
            if (!current.isJsonObject) fail("AND-BIND-007", "嵌套值签名对象路径无效")
            val name = last.asString
            if (!current.asJsonObject.has(name)) fail("AND-BIND-007", "嵌套值签名字段不存在：$name")
            current.asJsonObject.add(name, replacement.deepCopy())
        }
    }

    private fun pathChild(owner: JsonElement, step: JsonElement): JsonElement =
        if (step.isJsonPrimitive && step.asJsonPrimitive.isNumber) {
            if (!owner.isJsonArray || step.asInt !in 0 until owner.asJsonArray.size()) {
                fail("AND-BIND-007", "嵌套值签名数组路径无效")
            }
            owner.asJsonArray[step.asInt]
        } else {
            if (!owner.isJsonObject || !owner.asJsonObject.has(step.asString)) {
                fail("AND-BIND-007", "嵌套值签名对象路径无效")
            }
            owner.asJsonObject.get(step.asString)
        }

    private fun validateValue(value: JsonElement, declaredType: String, constraints: JsonObject, label: String) {
        val optional = declaredType.startsWith("optional<") && declaredType.endsWith('>')
        val type = if (optional) declaredType.substring(9, declaredType.length - 1) else declaredType
        if (value.isJsonNull) {
            if (!optional && type !in setOf("any", "json", "json_value", "unit", "null")) {
                fail("AND-BIND-011", "Player 控件“$label”的值不符合类型 $declaredType")
            }
            return
        }
        val valid = when {
            type in setOf("any", "json", "json_value", "message_value") -> true
            type == "bool" -> value.isJsonPrimitive && value.asJsonPrimitive.isBoolean
            type == "int64" -> value.isJsonPrimitive && value.asJsonPrimitive.isNumber && runCatching {
                value.asBigDecimal.toBigIntegerExact()
            }.isSuccess
            type in setOf("float64", "percentage") -> value.isJsonPrimitive && value.asJsonPrimitive.isNumber
            type in setOf("string", "relative_path", "url", "timezone", "date", "datetime", "time", "time_of_day", "key_chord") || type.startsWith("enum<") -> value.isJsonPrimitive && value.asJsonPrimitive.isString
            type == "duration" -> value.isJsonPrimitive && value.asJsonPrimitive.isNumber ||
                value.isJsonObject && value.asJsonObject.string("kind") == "duration"
            type == "point" -> coordinates(value, setOf("x", "y"))
            type == "rect" -> coordinates(value, setOf("x", "y", "width", "height"))
            type in setOf("path", "gesture_path") -> value.isJsonArray && value.asJsonArray.all { coordinates(it, setOf("x", "y")) }
            type.startsWith("asset_ref") -> reference(value, "asset_id")
            type.startsWith("file_ref") -> reference(value, "uri") && value.asJsonObject.string("kind") == "file_ref"
            type.startsWith("directory_ref") -> reference(value, "uri") && value.asJsonObject.string("kind") == "directory_ref"
            type.startsWith("list<") -> value.isJsonArray
            type.startsWith("map<") || type.startsWith("record<") -> value.isJsonObject
            type == "target_ref" -> reference(value, "target_id")
            else -> value.isJsonObject
        }
        if (!valid) fail("AND-BIND-011", "Player 控件“$label”的值不符合类型 $declaredType")
        if (value.isJsonPrimitive && value.asJsonPrimitive.isNumber) {
            val number = value.asBigDecimal
            constraints.get("minimum")?.takeUnless(JsonElement::isJsonNull)?.asBigDecimal?.let {
                if (number < it) fail("AND-BIND-012", "Player 控件“$label”的值小于最小值")
            }
            constraints.get("maximum")?.takeUnless(JsonElement::isJsonNull)?.asBigDecimal?.let {
                if (number > it) fail("AND-BIND-012", "Player 控件“$label”的值大于最大值")
            }
        }
        if (value.isJsonPrimitive && value.asJsonPrimitive.isString) {
            val length = value.asString.codePointCount(0, value.asString.length)
            if (constraints.has("min_length") && length < constraints.get("min_length").asInt) fail("AND-BIND-012", "Player 控件“$label”的文本过短")
            if (constraints.has("max_length") && length > constraints.get("max_length").asInt) fail("AND-BIND-012", "Player 控件“$label”的文本过长")
        }
        if (constraints.get("choices")?.isJsonArray == true) {
            val allowed = constraints.getAsJsonArray("choices").any { option ->
                val candidate = option.takeIf(JsonElement::isJsonObject)?.asJsonObject?.get("value") ?: option
                candidate == value
            }
            if (!allowed) fail("AND-BIND-012", "Player 控件“$label”的值不在允许选项中")
        }
    }

    private fun coordinates(value: JsonElement, fields: Set<String>): Boolean =
        value.isJsonObject && fields.all { name ->
            value.asJsonObject.get(name)?.let { it.isJsonPrimitive && it.asJsonPrimitive.isNumber } == true
        }

    private fun reference(value: JsonElement, field: String): Boolean =
        value.isJsonObject && value.asJsonObject.get(field)?.let {
            it.isJsonPrimitive && it.asString.isNotBlank()
        } == true

    private fun fail(code: String, message: String): Nothing = throw RuntimeFailure(code, message)
}
