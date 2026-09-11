package com.easycode.player.runtime

import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import java.math.BigDecimal

data class EvaluationScope(
    val locals: MutableMap<String, Any?>,
    val project: MutableMap<String, Any?>,
)

class EcirValueEvaluator(private val control: RuntimeControl) {
    fun evaluate(value: JsonElement?, scope: EvaluationScope): Any? {
        if (value == null || value.isJsonNull) return null
        if (value.isJsonPrimitive) return JsonSupport.toAny(value)
        if (value.isJsonArray) return value.asJsonArray.map { evaluate(it, scope) }
        val objectValue = value.asJsonObject
        return when (val kind = objectValue.string("kind")) {
            "duration" -> objectValue.get("milliseconds")?.let(JsonSupport::toAny)
            "reference" -> reference(objectValue, scope)
            "member_access" -> member(evaluate(objectValue.get("source"), scope), objectValue.string("field_id"))
            "list" -> objectValue.array("items").map { evaluate(it, scope) }
            "map" -> mapValue(objectValue, scope)
            "record" -> objectValue.obj("fields").entrySet().associate { it.key to evaluate(it.value, scope) }
            "json" -> JsonSupport.toAny(objectValue.get("value"))
            "compare" -> compare(objectValue, scope)
            "condition_group" -> conditionGroup(objectValue, scope)
            "not" -> !truthy(evaluate(objectValue.get("condition"), scope))
            "operation" -> PureOperations(this, control).execute(objectValue, scope)
            "selector" -> throw RuntimeFailure("runtime.selector_scope", "逐项选择器只能由集合纯值操作执行")
            "date", "datetime", "time" -> objectValue.get("value")?.let(JsonSupport::toAny)?.toString().orEmpty()
            "asset_ref", "target_ref", "entity_ref", "point", "rect", "path" -> objectValue.entrySet().associate { entry ->
                entry.key to if (entry.key == "kind") kind else evaluate(entry.value, scope)
            }
            "member" -> member(evaluate(objectValue.get("owner"), scope), objectValue.string("name"))
            "subscript" -> subscript(
                evaluate(objectValue.get("owner"), scope),
                evaluate(objectValue.get("key"), scope),
            )
            "unary" -> unary(objectValue, scope)
            "boolean" -> boolean(objectValue, scope)
            "binary" -> binary(objectValue, scope)
            "call", "expression" -> throw RuntimeFailure(
                "runtime.expression_unsupported",
                "此位置的表达式不能由 Android Runtime 求值",
            )
            else -> objectValue.entrySet().associate { it.key to evaluate(it.value, scope) }
        }
    }

    fun evaluateSelector(
        selector: JsonElement?,
        scope: EvaluationScope,
        bindings: Map<String, Any?>,
    ): Any? {
        if (selector?.isJsonObject != true || selector.asJsonObject.string("kind") != "selector") {
            throw RuntimeFailure("runtime.operation_input", "纯值操作的逐项选择器无效")
        }
        val scopedLocals = scope.locals.toMutableMap()
        for (binding in selector.asJsonObject.array("bindings")) {
            if (!binding.isJsonObject) throw RuntimeFailure("runtime.operation_input", "逐项选择器绑定无效")
            val record = binding.asJsonObject
            val role = record.string("role")
            val symbolId = record.string("symbol_id")
            if (role !in bindings || symbolId.isBlank()) {
                throw RuntimeFailure("runtime.operation_input", "逐项选择器缺少绑定：$role")
            }
            scopedLocals[symbolId] = bindings[role]
        }
        return evaluate(selector.asJsonObject.get("expression"), EvaluationScope(scopedLocals, scope.project))
    }

    private fun reference(value: JsonObject, scope: EvaluationScope): Any? {
        val name = value.string("symbol_id").ifBlank { value.string("variable_id").ifBlank { value.string("name") } }
        val namespace = if (value.string("scope", "local") == "project") scope.project else scope.locals
        if (name !in namespace) throw RuntimeFailure("runtime.variable_unset", "变量尚未赋值：$name")
        return namespace[name]
    }

    private fun mapValue(value: JsonObject, scope: EvaluationScope): Map<Any?, Any?> {
        val result = linkedMapOf<Any?, Any?>()
        for (entry in value.array("entries")) {
            if (!entry.isJsonObject) throw RuntimeFailure("runtime.map_invalid", "字典条目格式无效")
            val key = evaluate(entry.asJsonObject.get("key"), scope)
            if (key in result) throw RuntimeFailure("runtime.map_duplicate_key", "字典中存在重复键")
            result[key] = evaluate(entry.asJsonObject.get("value"), scope)
        }
        return result
    }

    private fun member(owner: Any?, field: String): Any? {
        if (owner == null) {
            throw RuntimeFailure(
                "runtime.optional_empty",
                "当前语句需要使用的结果为空，无法继续；如果无结果是正常情况，请先判断“有结果”。",
            )
        }
        if (owner is Map<*, *>) {
            if (field !in owner) throw RuntimeFailure("runtime.member_missing", "记录不包含字段：$field")
            return owner[field]
        }
        throw RuntimeFailure("runtime.member_missing", "值不包含字段：$field")
    }

    private fun subscript(owner: Any?, key: Any?): Any? = when (owner) {
        is List<*> -> owner[(key as Number).toInt()]
        is Map<*, *> -> owner[key]
        is String -> owner[(key as Number).toInt()].toString()
        else -> throw RuntimeFailure("runtime.subscript_invalid", "值不支持下标访问")
    }

    private fun compare(value: JsonObject, scope: EvaluationScope): Boolean {
        var left = evaluate(value.get("left"), scope)
        var right = evaluate(value.get("right"), scope)
        if (value.string("operand_type") == "datetime") {
            val parsedLeft = parseComparableDateTime(left?.toString().orEmpty())
            val parsedRight = parseComparableDateTime(right?.toString().orEmpty())
            if (parsedLeft.first != parsedRight.first) {
                throw RuntimeFailure("time.timezone_mismatch", "两个日期与时间必须同时包含或同时不包含时区")
            }
            left = parsedLeft.second
            right = parsedRight.second
        }
        return when (value.string("operator")) {
            "eq", "equal" -> equivalent(left, right)
            "ne", "not_equal" -> !equivalent(left, right)
            "lt", "less" -> compareValues(left, right) < 0
            "lte", "less_equal" -> compareValues(left, right) <= 0
            "gt", "greater" -> compareValues(left, right) > 0
            "gte", "greater_equal" -> compareValues(left, right) >= 0
            "in" -> contains(right, left)
            "not_in" -> !contains(right, left)
            else -> throw RuntimeFailure("runtime.operation_unsupported", "不支持的比较操作：${value.string("operator")}")
        }
    }

    private fun parseComparableDateTime(raw: String): Pair<Boolean, Comparable<Any>> {
        @Suppress("UNCHECKED_CAST")
        return try {
            true to (java.time.OffsetDateTime.parse(raw).toInstant() as Comparable<Any>)
        } catch (_: java.time.format.DateTimeParseException) {
            try {
                false to (java.time.LocalDateTime.parse(raw) as Comparable<Any>)
            } catch (error: java.time.format.DateTimeParseException) {
                throw RuntimeFailure("time.value_invalid", "日期与时间值无效", cause = error)
            }
        }
    }

    private fun conditionGroup(value: JsonObject, scope: EvaluationScope): Boolean {
        val conditions = value.array("conditions")
        return when (value.string("operator")) {
            "all" -> conditions.all { truthy(evaluate(it, scope)) }
            "any" -> conditions.any { truthy(evaluate(it, scope)) }
            else -> throw RuntimeFailure("runtime.operation_unsupported", "条件组只支持 all/any")
        }
    }

    private fun unary(value: JsonObject, scope: EvaluationScope): Any? {
        val operand = evaluate(value.get("operand"), scope)
        return when (value.string("operator")) {
            "not" -> !truthy(operand)
            "negative" -> -number(operand).toDouble()
            "positive" -> number(operand).toDouble()
            else -> throw RuntimeFailure("runtime.operation_unsupported", "一元操作不受支持")
        }
    }

    private fun boolean(value: JsonObject, scope: EvaluationScope): Boolean = when (value.string("operator")) {
        "and" -> value.array("values").all { truthy(evaluate(it, scope)) }
        "or" -> value.array("values").any { truthy(evaluate(it, scope)) }
        else -> throw RuntimeFailure("runtime.operation_unsupported", "布尔操作不受支持")
    }

    private fun binary(value: JsonObject, scope: EvaluationScope): Any {
        val left = evaluate(value.get("left"), scope)
        val right = evaluate(value.get("right"), scope)
        return when (value.string("operator")) {
            "add" -> if (left is String || right is String) "$left$right" else numeric(left, right) { a, b -> a + b }
            "subtract" -> numeric(left, right) { a, b -> a - b }
            "multiply" -> numeric(left, right) { a, b -> a * b }
            "divide" -> numeric(left, right) { a, b ->
                if (b.compareTo(BigDecimal.ZERO) == 0) throw RuntimeFailure("runtime.divide_by_zero", "除数不能为零")
                a.divide(b, 16, java.math.RoundingMode.HALF_EVEN).stripTrailingZeros()
            }
            "modulo" -> numeric(left, right) { a, b -> a.remainder(b) }
            else -> throw RuntimeFailure("runtime.operation_unsupported", "二元操作不受支持")
        }
    }

    private fun numeric(left: Any?, right: Any?, operation: (BigDecimal, BigDecimal) -> BigDecimal): Any {
        val result = operation(decimal(left), decimal(right))
        return if (result.scale() <= 0) result.toLong() else result.toDouble()
    }

    companion object {
        fun truthy(value: Any?): Boolean = when (value) {
            null -> false
            is Boolean -> value
            is Number -> value.toDouble() != 0.0
            is String -> value.isNotEmpty()
            is Collection<*> -> value.isNotEmpty()
            is Map<*, *> -> value.isNotEmpty()
            else -> true
        }

        fun equivalent(left: Any?, right: Any?): Boolean =
            if (left is Number && right is Number) decimal(left).compareTo(decimal(right)) == 0 else left == right

        fun compareValues(left: Any?, right: Any?): Int = when {
            left is Number && right is Number -> decimal(left).compareTo(decimal(right))
            left is String && right is String -> left.compareTo(right)
            left is Boolean && right is Boolean -> left.compareTo(right)
            left is Comparable<*> && right != null && left::class == right::class -> {
                @Suppress("UNCHECKED_CAST")
                (left as Comparable<Any>).compareTo(right)
            }
            else -> throw RuntimeFailure("runtime.compare_invalid", "值之间不可比较")
        }

        fun number(value: Any?): Number = value as? Number
            ?: throw RuntimeFailure("runtime.argument_type", "需要数值")

        fun decimal(value: Any?): BigDecimal = when (value) {
            is BigDecimal -> value
            is Number -> value.toString().toBigDecimal()
            else -> throw RuntimeFailure("runtime.argument_type", "需要数值")
        }

        fun contains(container: Any?, value: Any?): Boolean = when (container) {
            is Collection<*> -> container.any { equivalent(it, value) }
            is Map<*, *> -> container.keys.any { equivalent(it, value) }
            is String -> value is String && container.contains(value)
            else -> false
        }
    }
}
