package com.easycode.player.runtime

import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import java.math.BigDecimal
import java.math.RoundingMode
import java.nio.charset.StandardCharsets
import java.time.Duration
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException
import java.util.Locale
import kotlin.math.ceil

internal class PureOperations(
    private val evaluator: EcirValueEvaluator,
    private val control: RuntimeControl,
) {
    private lateinit var operation: JsonObject
    private lateinit var scope: EvaluationScope
    private val evaluated = mutableMapOf<String, Any?>()

    fun execute(operation: JsonObject, scope: EvaluationScope): Any? {
        this.operation = operation
        this.scope = scope
        evaluated.clear()
        val id = operation.string("operation_id")
        return when {
            id.startsWith("core.number_") -> numberOperation(id)
            id == "core.value_to_text.v1" -> stableValueText(input("value"))
            id.startsWith("core.text_") -> textOperation(id)
            id.startsWith("core.datetime_") || id.startsWith("core.date_") || id.startsWith("core.time_") -> temporalOperation(id)
            id.startsWith("core.duration_from_") -> durationFromAmount(id)
            id == "core.duration_poll_count.v1" -> durationPollCount()
            id == "core.optional_has_value.v1" -> input("value") != null
            id == "core.optional_default.v1" -> input("value") ?: input("default")
            id == "core.select.v1" -> if (EcirValueEvaluator.truthy(input("condition"))) input("when_true") else input("when_false")
            id == "core.point_offset.v1" -> pointOffset()
            id == "core.point_scale.v1" -> pointScale()
            id == "core.rect_center.v1" -> rectCenter()
            id == "core.rect_scale.v1" -> rectScale()
            id == "core.color_matches.v1" -> colorMatches()
            id.startsWith("core.list_") -> listOperation(id)
            id.startsWith("core.map_") -> mapOperation(id)
            id.startsWith("core.json_") -> jsonOperation(id)
            id == "core.file_ref_child.v1" -> fileReferenceChild()
            else -> throw RuntimeFailure("runtime.operation_unsupported", "纯值操作尚未实现：$id")
        }
    }

    private fun raw(name: String): JsonElement {
        val matches = operation.obj("inputs").entrySet().filter { it.key.endsWith(".input.$name") }
        if (matches.size != 1) {
            throw RuntimeFailure(
                "runtime.operation_input",
                "纯值操作 ${operation.string("operation_id")} 缺少或重复输入：$name",
            )
        }
        return matches.single().value
    }

    private fun input(name: String): Any? = evaluated.getOrPut(name) { evaluator.evaluate(raw(name), scope) }

    private fun selector(name: String, bindings: Map<String, Any?>): Any? =
        evaluator.evaluateSelector(raw(name), scope, bindings)

    private fun numberOperation(id: String): Any = when (id) {
        "core.number_add.v1" -> numeric("left", "right") { a, b -> a + b }
        "core.number_subtract.v1" -> numeric("left", "right") { a, b -> a - b }
        "core.number_multiply.v1" -> numeric("left", "right") { a, b -> a * b }
        "core.number_divide.v1" -> numeric("left", "right") { a, b ->
            if (b.compareTo(BigDecimal.ZERO) == 0) throw RuntimeFailure("runtime.divide_by_zero", "除数不能为零")
            a.divide(b, 16, RoundingMode.HALF_EVEN).stripTrailingZeros()
        }
        "core.number_modulo.v1" -> numeric("left", "right") { a, b ->
            if (b.compareTo(BigDecimal.ZERO) == 0) throw RuntimeFailure("runtime.divide_by_zero", "除数不能为零")
            a.remainder(b)
        }
        "core.number_min.v1" -> if (EcirValueEvaluator.compareValues(input("left"), input("right")) <= 0) input("left")!! else input("right")!!
        "core.number_max.v1" -> if (EcirValueEvaluator.compareValues(input("left"), input("right")) >= 0) input("left")!! else input("right")!!
        "core.number_clamp.v1" -> {
            val value = EcirValueEvaluator.decimal(input("value"))
            val minimum = EcirValueEvaluator.decimal(input("minimum"))
            val maximum = EcirValueEvaluator.decimal(input("maximum"))
            if (minimum > maximum) throw RuntimeFailure("runtime.argument_range", "范围下限不能大于上限")
            numberResult(value.coerceIn(minimum, maximum))
        }
        "core.number_round.v1" -> {
            val digits = EcirValueEvaluator.number(input("digits")).toInt()
            numberResult(EcirValueEvaluator.decimal(input("value")).setScale(digits, RoundingMode.HALF_EVEN))
        }
        "core.number_to_int.v1" -> EcirValueEvaluator.number(input("value")).toLong()
        "core.number_to_float.v1" -> EcirValueEvaluator.number(input("value")).toDouble()
        else -> throw RuntimeFailure("runtime.operation_unsupported", "数值操作尚未实现：$id")
    }

    private fun numeric(left: String, right: String, block: (BigDecimal, BigDecimal) -> BigDecimal): Any =
        numberResult(block(EcirValueEvaluator.decimal(input(left)), EcirValueEvaluator.decimal(input(right))))

    private fun numberResult(value: BigDecimal): Any =
        if (value.stripTrailingZeros().scale() <= 0) value.toLong() else value.toDouble()

    private fun textOperation(id: String): Any? = when (id) {
        "core.text_concat.v1" -> input("left").toString() + input("right").toString()
        "core.text_replace.v1" -> input("text").toString().replace(input("search").toString(), input("replacement").toString())
        "core.text_slice.v1" -> sliceString(
            input("text").toString(),
            EcirValueEvaluator.number(input("start")).toInt(),
            EcirValueEvaluator.number(input("end")).toInt(),
        )
        "core.text_lower.v1" -> input("text").toString().lowercase()
        "core.text_upper.v1" -> input("text").toString().uppercase()
        "core.text_trim.v1" -> input("text").toString().trim()
        "core.text_length.v1" -> input("text").toString().codePointCount(0, input("text").toString().length)
        "core.text_to_int.v1" -> input("text").toString().trim().let { text ->
            if (!PORTABLE_INTEGER.matches(text)) null else text.toLongOrNull()
        }
        "core.text_to_float.v1" -> input("text").toString().trim().let { text ->
            if (!PORTABLE_FLOAT.matches(text)) null else text.toDoubleOrNull()?.takeIf(Double::isFinite)
        }
        "core.text_split.v1" -> splitPreservingEmpty(input("text").toString(), input("separator").toString())
        "core.text_join.v1" -> {
            val values = list(input("list"))
            if (values.any { it !is String }) {
                throw RuntimeFailure("runtime.argument_type", "连接文本需要文本列表")
            }
            values.joinToString(input("separator").toString())
        }
        "core.text_matches.v1" -> {
            val actual = input("actual").toString()
            val expected = input("expected").toString()
            when (input("mode").toString()) {
                "exact" -> actual == expected
                "contains" -> actual.contains(expected)
                "regex" -> try {
                    Regex(expected).containsMatchIn(actual)
                } catch (error: IllegalArgumentException) {
                    throw RuntimeFailure("text.regex_invalid", "正则表达式无效：${error.message}", cause = error)
                }
                else -> throw RuntimeFailure("runtime.argument_range", "文字匹配方式无效")
            }
        }
        "core.text_regex_extract.v1" -> regex(input("pattern").toString()).find(input("text").toString())?.let { match ->
            val group = EcirValueEvaluator.number(input("group")).toInt()
            if (group !in 0 until match.groups.size) throw RuntimeFailure("text.regex_group_invalid", "正则分组序号超出范围")
            match.groups[group]?.value.orEmpty()
        }
        "core.text_regex_groups.v1" -> regex(input("pattern").toString()).find(input("text").toString())
            ?.groupValues?.drop(1).orEmpty()
        "core.text_extract_first_int.v1" -> Regex("[+-]?[0-9]+").find(input("text").toString())
            ?.value?.toLongOrNull()
        "core.text_parse_datetime.v1" -> try {
            val text = input("text").toString()
            val format = formatter(input("pattern").toString())
            try { OffsetDateTime.parse(text, format).toString() } catch (_: DateTimeParseException) {
                LocalDateTime.parse(text, format).toString()
            }
        } catch (_: DateTimeParseException) {
            null
        }
        else -> throw RuntimeFailure("runtime.operation_unsupported", "文字操作尚未实现：$id")
    }

    private fun regex(pattern: String): Regex = try {
        Regex(pattern)
    } catch (error: IllegalArgumentException) {
        throw RuntimeFailure("text.regex_invalid", "正则表达式无效：${error.message}", cause = error)
    }

    private fun formatter(pattern: String): DateTimeFormatter = try {
        if (Regex("[A-Za-z]+").findAll(pattern).any { it.value !in setOf("yyyy", "MM", "dd", "HH", "mm", "ss", "SSS", "XXX") }) {
            throw IllegalArgumentException("只支持 yyyy MM dd HH mm ss SSS XXX")
        }
        DateTimeFormatter.ofPattern(pattern, Locale.ROOT)
    } catch (error: IllegalArgumentException) {
        throw RuntimeFailure("time.pattern_invalid", "日期时间格式无效：${error.message}", cause = error)
    }

    private fun temporalOperation(id: String): Any = when (id) {
        "core.datetime_add_duration.v1", "core.datetime_subtract_duration.v1" -> {
            val raw = input("datetime").toString()
            val milliseconds = EcirValueEvaluator.number(input("duration")).toLong() *
                if (id == "core.datetime_subtract_duration.v1") -1L else 1L
            addDateTime(raw, milliseconds)
        }
        "core.datetime_difference.v1" -> {
            val later = parseDateTimeInstant(input("later").toString())
            val earlier = parseDateTimeInstant(input("earlier").toString())
            if (later.first != earlier.first) throw RuntimeFailure("time.timezone_mismatch", "两个日期与时间必须同时包含或同时不包含时区")
            Duration.between(earlier.second, later.second).toMillis()
        }
        "core.datetime_format.v1" -> {
            val raw = input("datetime").toString()
            val format = formatter(input("pattern").toString())
            try { OffsetDateTime.parse(raw).format(format) } catch (_: DateTimeParseException) {
                try { LocalDateTime.parse(raw).format(format) } catch (error: DateTimeParseException) {
                    throw RuntimeFailure("time.value_invalid", "日期与时间值无效", cause = error)
                }
            }
        }
        "core.date_add_days.v1" -> try {
            LocalDate.parse(input("date").toString()).plusDays(EcirValueEvaluator.number(input("days")).toLong()).toString()
        } catch (error: DateTimeParseException) {
            throw RuntimeFailure("time.value_invalid", "日期值无效", cause = error)
        }
        "core.date_difference.v1" -> try {
            java.time.temporal.ChronoUnit.DAYS.between(
                LocalDate.parse(input("earlier").toString()), LocalDate.parse(input("later").toString()),
            )
        } catch (error: DateTimeParseException) {
            throw RuntimeFailure("time.value_invalid", "日期值无效", cause = error)
        }
        "core.time_add_duration.v1" -> try {
            LocalTime.parse(input("time").toString()).plusNanos(EcirValueEvaluator.number(input("duration")).toLong() * 1_000_000L).toString()
        } catch (error: DateTimeParseException) {
            throw RuntimeFailure("time.value_invalid", "时间值无效", cause = error)
        }
        else -> throw RuntimeFailure("runtime.operation_unsupported", "时间操作尚未实现：$id")
    }

    private fun addDateTime(raw: String, milliseconds: Long): String = try {
        OffsetDateTime.parse(raw).plusNanos(milliseconds * 1_000_000L).toString()
    } catch (_: DateTimeParseException) {
        try { LocalDateTime.parse(raw).plusNanos(milliseconds * 1_000_000L).toString() } catch (error: DateTimeParseException) {
            throw RuntimeFailure("time.value_invalid", "日期与时间值无效", cause = error)
        }
    }

    private fun parseDateTimeInstant(raw: String): Pair<Boolean, java.time.temporal.Temporal> = try {
        true to OffsetDateTime.parse(raw)
    } catch (_: DateTimeParseException) {
        try { false to LocalDateTime.parse(raw) } catch (error: DateTimeParseException) {
            throw RuntimeFailure("time.value_invalid", "日期与时间值无效", cause = error)
        }
    }

    private fun durationPollCount(): Long {
        val timeout = EcirValueEvaluator.number(input("timeout")).toDouble()
        val interval = EcirValueEvaluator.number(input("interval")).toDouble()
        if (timeout < 0.0 || interval <= 0.0) throw RuntimeFailure("target.invalid_duration", "轮询超时和间隔配置无效")
        return ceil(timeout / interval).toLong().coerceAtLeast(0L) + 1L
    }

    private fun durationFromAmount(id: String): Long {
        val amount = EcirValueEvaluator.decimal(input("amount"))
        if (amount < BigDecimal.ZERO) {
            throw RuntimeFailure("runtime.argument_range", "持续时间不能小于 0")
        }
        val multiplier = when (id) {
            "core.duration_from_milliseconds.v1" -> BigDecimal.ONE
            "core.duration_from_seconds.v1" -> BigDecimal(1_000)
            "core.duration_from_minutes.v1" -> BigDecimal(60_000)
            else -> throw RuntimeFailure("runtime.operation_unsupported", "持续时间操作尚未实现：$id")
        }
        return amount.multiply(multiplier).toLong()
    }

    private fun pointOffset(): Map<String, Any?> {
        val point = stringMap(input("point"))
        val offset = stringMap(input("offset"))
        return linkedMapOf(
            "kind" to "point",
            "x" to addNumbers(point["x"], offset["x"]),
            "y" to addNumbers(point["y"], offset["y"]),
        )
    }

    private fun pointScale(): Map<String, Any?> {
        val point = stringMap(input("point"))
        val scaleX = EcirValueEvaluator.decimal(input("scale_x"))
        val scaleY = EcirValueEvaluator.decimal(input("scale_y"))
        return LinkedHashMap(point).apply {
            this["kind"] = "point"
            this["x"] = numberResult(EcirValueEvaluator.decimal(point["x"]) * scaleX)
            this["y"] = numberResult(EcirValueEvaluator.decimal(point["y"]) * scaleY)
        }
    }

    private fun rectCenter(): Map<String, Any?> {
        val rect = stringMap(input("rect"))
        return linkedMapOf(
            "kind" to "point",
            "x" to EcirValueEvaluator.number(rect["x"]).toDouble() + EcirValueEvaluator.number(rect["width"]).toDouble() / 2.0,
            "y" to EcirValueEvaluator.number(rect["y"]).toDouble() + EcirValueEvaluator.number(rect["height"]).toDouble() / 2.0,
        )
    }

    private fun rectScale(): Map<String, Any?> {
        val rect = stringMap(input("rect"))
        val scaleX = EcirValueEvaluator.decimal(input("scale_x"))
        val scaleY = EcirValueEvaluator.decimal(input("scale_y"))
        return LinkedHashMap(rect).apply {
            this["kind"] = "rect"
            this["x"] = numberResult(EcirValueEvaluator.decimal(rect["x"]) * scaleX)
            this["y"] = numberResult(EcirValueEvaluator.decimal(rect["y"]) * scaleY)
            this["width"] = numberResult(EcirValueEvaluator.decimal(rect["width"]) * scaleX)
            this["height"] = numberResult(EcirValueEvaluator.decimal(rect["height"]) * scaleY)
        }
    }

    private fun colorMatches(): Boolean {
        val actual = stringMap(input("actual"))
        val expected = stringMap(input("expected"))
        val tolerance = exactInt(input("tolerance"), "runtime.color_tolerance_invalid", "颜色容差")
        if (tolerance !in 0..255) {
            throw RuntimeFailure("runtime.color_tolerance_invalid", "颜色容差必须为 0 至 255 的整数")
        }
        return listOf("red", "green", "blue", "alpha").all { field ->
            val left = exactInt(actual["color.field.$field"], "runtime.color_invalid", "颜色 $field 通道")
            val right = exactInt(expected["color.field.$field"], "runtime.color_invalid", "颜色 $field 通道")
            left in 0..255 && right in 0..255 && kotlin.math.abs(left - right) <= tolerance
        }
    }

    private fun exactInt(value: Any?, errorId: String, label: String): Int {
        val number = value as? Number ?: throw RuntimeFailure(errorId, "$label 必须是整数")
        val decimal = number.toDouble()
        if (!decimal.isFinite() || decimal % 1.0 != 0.0 || decimal < Int.MIN_VALUE || decimal > Int.MAX_VALUE) {
            throw RuntimeFailure(errorId, "$label 必须是整数")
        }
        return decimal.toInt()
    }

    private fun stableValueText(value: Any?): String = when (value) {
        is Boolean -> if (value) "true" else "false"
        is Byte, is Short, is Int, is Long -> value.toString()
        is Float -> if (value.isFinite()) BigDecimal(value.toString()).stripTrailingZeros().toPlainString()
            else throw RuntimeFailure("runtime.argument_type", "只能把有限数值转换为文本")
        is Double -> if (value.isFinite()) BigDecimal(value.toString()).stripTrailingZeros().toPlainString()
            else throw RuntimeFailure("runtime.argument_type", "只能把有限数值转换为文本")
        is BigDecimal -> value.stripTrailingZeros().toPlainString()
        is Map<*, *> -> when (value["kind"]?.toString()) {
            "date", "datetime", "time", "time_of_day" -> value["value"]?.toString().orEmpty()
            "duration" -> stableDurationText(value["milliseconds"])
            else -> throw RuntimeFailure("runtime.argument_type", "该结构化值不能直接转换为文本")
        }
        null -> throw RuntimeFailure("runtime.argument_type", "无结果不能直接转换为文本")
        else -> value.toString()
    }

    private fun splitPreservingEmpty(text: String, separator: String): List<String> {
        if (separator.isEmpty()) throw RuntimeFailure("text.separator_empty", "文本分隔符不能为空")
        val result = mutableListOf<String>()
        var start = 0
        while (true) {
            val index = text.indexOf(separator, start)
            if (index < 0) {
                result += text.substring(start)
                return result
            }
            result += text.substring(start, index)
            start = index + separator.length
        }
    }

    private fun stableDurationText(value: Any?): String {
        val number = value as? Number
            ?: throw RuntimeFailure("runtime.argument_type", "持续时间的毫秒值无效")
        val decimal = when (number) {
            is Float -> if (number.isFinite()) BigDecimal(number.toString()) else null
            is Double -> if (number.isFinite()) BigDecimal(number.toString()) else null
            else -> BigDecimal(number.toString())
        } ?: throw RuntimeFailure("runtime.number_not_finite", "只有有限持续时间可以转为文本")
        return decimal.stripTrailingZeros().toPlainString().let { if (it == "-0") "0" else it }
    }

    private companion object {
        val PORTABLE_INTEGER = Regex("[+-]?[0-9]+")
        val PORTABLE_FLOAT = Regex("[+-]?(?:[0-9]+(?:\\.[0-9]*)?|\\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
    }

    private fun listOperation(id: String): Any? {
        val items = list(input("list"))
        budget(items.size)
        return when (id) {
            "core.list_is_empty.v1" -> items.isEmpty()
            "core.list_length.v1" -> items.size.toLong()
            "core.list_contains.v1" -> items.any { EcirValueEvaluator.equivalent(it, input("value")) }
            "core.list_first.v1" -> items.firstOrNull()
            "core.list_last.v1" -> items.lastOrNull()
            "core.list_get.v1" -> items.getOrNull(EcirValueEvaluator.number(input("index")).toInt())
            "core.list_append.v1" -> items + input("value")
            "core.list_prepend.v1" -> listOf(input("value")) + items
            "core.list_insert.v1" -> items.toMutableList().also { it.add(index(items, input("index"), true), input("value")) }
            "core.list_replace.v1" -> items.toMutableList().also { it[index(items, input("index"), false)] = input("value") }
            "core.list_remove_at.v1" -> items.toMutableList().also { it.removeAt(index(items, input("index"), false)) }
            "core.list_clear.v1" -> emptyList<Any?>()
            "core.list_reverse.v1" -> items.reversed()
            "core.list_slice.v1" -> sliceList(items, input("start"), input("end"))
            "core.list_concat.v1" -> (items + list(input("other"))).also { budget(it.size) }
            "core.list_distinct.v1" -> items.fold(mutableListOf<Any?>()) { result, item ->
                if (result.none { EcirValueEvaluator.equivalent(it, item) }) result += item
                result
            }
            "core.list_sum.v1" -> numberResult(items.fold(BigDecimal.ZERO) { total, item -> total + EcirValueEvaluator.decimal(item) })
            "core.list_average.v1" -> if (items.isEmpty()) null else numberResult(
                items.fold(BigDecimal.ZERO) { total, item -> total + EcirValueEvaluator.decimal(item) }
                    .divide(items.size.toBigDecimal(), 16, RoundingMode.HALF_EVEN),
            )
            "core.list_min.v1" -> items.minWithOrNull(::compareAny)
            "core.list_max.v1" -> items.maxWithOrNull(::compareAny)
            "core.list_filter.v1" -> items.filterIndexed { index, item ->
                checkpoint(index)
                EcirValueEvaluator.truthy(selector("predicate", mapOf("item" to item, "index" to index.toLong())))
            }
            "core.list_map.v1" -> items.mapIndexed { index, item ->
                checkpoint(index)
                selector("transform", mapOf("item" to item, "index" to index.toLong()))
            }
            "core.list_sort_by.v1" -> items.mapIndexed { index, item ->
                checkpoint(index)
                Triple(selector("key_selector", mapOf("item" to item, "index" to index.toLong())), index, item)
            }.sortedWith { left, right ->
                val compared = compareAny(left.first, right.first)
                val stable = if (compared == 0) left.second.compareTo(right.second) else compared
                if (EcirValueEvaluator.truthy(input("descending"))) -stable else stable
            }.map { it.third }
            "core.list_group_by.v1" -> linkedMapOf<Any?, MutableList<Any?>>().also { grouped ->
                items.forEachIndexed { index, item ->
                    checkpoint(index)
                    val key = selector("key_selector", mapOf("item" to item, "index" to index.toLong()))
                    grouped.getOrPut(key) { mutableListOf() }.add(item)
                }
            }
            "core.list_flatten.v1" -> items.flatMapIndexed { index, item ->
                checkpoint(index)
                list(item)
            }.also { budget(it.size) }
            "core.list_zip.v1" -> items.zip(list(input("other"))).map { (left, right) ->
                linkedMapOf("zip_pair.field.left" to left, "zip_pair.field.right" to right)
            }
            "core.list_find_first.v1" -> items.withIndex().firstOrNull { (index, item) ->
                checkpoint(index)
                EcirValueEvaluator.truthy(selector("predicate", mapOf("item" to item, "index" to index.toLong())))
            }?.value
            "core.list_any.v1" -> items.withIndex().any { (index, item) ->
                checkpoint(index)
                EcirValueEvaluator.truthy(selector("predicate", mapOf("item" to item, "index" to index.toLong())))
            }
            "core.list_all.v1" -> items.withIndex().all { (index, item) ->
                checkpoint(index)
                EcirValueEvaluator.truthy(selector("predicate", mapOf("item" to item, "index" to index.toLong())))
            }
            "core.list_count_match.v1" -> items.withIndex().count { (index, item) ->
                checkpoint(index)
                EcirValueEvaluator.truthy(selector("predicate", mapOf("item" to item, "index" to index.toLong())))
            }.toLong()
            "core.list_index_by.v1" -> linkedMapOf<Any?, Any?>().also { indexed ->
                items.forEachIndexed { index, item ->
                    checkpoint(index)
                    val key = selector("key_selector", mapOf("item" to item, "index" to index.toLong()))
                    if (key in indexed) throw RuntimeFailure("runtime.map_duplicate_key", "按依据建立索引时遇到重复键")
                    indexed[key] = item
                }
            }
            else -> throw RuntimeFailure("runtime.operation_unsupported", "列表操作尚未实现：$id")
        }
    }

    private fun mapOperation(id: String): Any? {
        val source = map(input("map"))
        budget(source.size)
        return when (id) {
            "core.map_has_key.v1" -> source.keys.any { EcirValueEvaluator.equivalent(it, input("key")) }
            "core.map_get.v1" -> source.entries.firstOrNull { EcirValueEvaluator.equivalent(it.key, input("key")) }?.value
            "core.map_set.v1" -> LinkedHashMap(source).apply { this[input("key")] = input("value") }
            "core.map_delete.v1" -> LinkedHashMap(source).apply {
                keys.firstOrNull { EcirValueEvaluator.equivalent(it, input("key")) }?.let(::remove)
            }
            "core.map_clear.v1" -> emptyMap<Any?, Any?>()
            "core.map_keys.v1" -> source.keys.toList()
            "core.map_values.v1" -> source.values.toList()
            "core.map_entries.v1" -> source.map { linkedMapOf("key" to it.key, "value" to it.value) }
            "core.map_merge.v1" -> mergeMaps(source, map(input("other")), input("conflict").toString())
            "core.map_filter.v1" -> linkedMapOf<Any?, Any?>().also { result ->
                source.entries.forEachIndexed { index, entry ->
                    checkpoint(index)
                    if (EcirValueEvaluator.truthy(selector("predicate", mapOf("key" to entry.key, "value" to entry.value)))) {
                        result[entry.key] = entry.value
                    }
                }
            }
            "core.map_map_values.v1" -> linkedMapOf<Any?, Any?>().also { result ->
                source.entries.forEachIndexed { index, entry ->
                    checkpoint(index)
                    result[entry.key] = selector("transform", mapOf("key" to entry.key, "value" to entry.value))
                }
            }
            "core.map_group_by.v1" -> linkedMapOf<Any?, MutableList<Map<String, Any?>>>().also { grouped ->
                source.entries.forEachIndexed { index, entry ->
                    checkpoint(index)
                    val group = selector("key_selector", mapOf("key" to entry.key, "value" to entry.value))
                    grouped.getOrPut(group) { mutableListOf() }.add(
                        linkedMapOf("map_entry.field.key" to entry.key, "map_entry.field.value" to entry.value),
                    )
                }
            }
            else -> throw RuntimeFailure("runtime.operation_unsupported", "字典操作尚未实现：$id")
        }
    }

    private fun jsonOperation(id: String): Any? = when (id) {
        "core.json_parse_text.v1" -> runCatching { JsonSupport.toAny(JsonSupport.parse(input("text").toString().toByteArray())) }.getOrNull()
        "core.json_validate_schema.v1" -> input("json").also { validateSchema(it, stringMap(input("schema")), "$") }
        "core.json_path_exists.v1" -> locate(input("json"), list(input("path"))).first
        "core.json_path_get.v1" -> locate(input("json"), list(input("path"))).second
        "core.json_path_set.v1" -> mutatePath(input("json"), list(input("path")), input("value"), delete = false)
        "core.json_path_delete.v1" -> mutatePath(input("json"), list(input("path")), null, delete = true)
        else -> throw RuntimeFailure("runtime.operation_unsupported", "JSON 操作尚未实现：$id")
    }

    private fun fileReferenceChild(): Map<String, Any?> {
        val directory = stringMap(input("directory"))
        if (directory["kind"] != "directory_ref") {
            throw RuntimeFailure("file.invalid_reference", "需要已授权的目录引用")
        }
        val platform = directory["platform"]?.toString().orEmpty()
        if (platform !in setOf("windows", "android")) {
            throw RuntimeFailure("file.platform_unsupported", "不支持的目录引用平台：${platform.ifBlank { "<空>" }}")
        }
        val authorizationRootId = directory["authorization_root_id"]?.toString().orEmpty()
        if (authorizationRootId.isBlank()) {
            throw RuntimeFailure("file.invalid_reference", "目录引用缺少授权根标识")
        }
        val resultType = operation.string("result_type")
        val requestedAccess = when (resultType) {
            "file_ref<read>" -> "read"
            "file_ref<write>" -> "write"
            else -> throw RuntimeFailure(
                "file.reference_capability_invalid",
                "不支持派生此文件引用能力：$resultType",
            )
        }
        val allowedParentAccess = if (requestedAccess == "read") setOf("read") else setOf("write", "create")
        val actualAccess = (directory["access"] as? List<*>)?.mapTo(mutableSetOf()) { it.toString() }.orEmpty()
        if (actualAccess.intersect(allowedParentAccess).isEmpty()) {
            throw RuntimeFailure("file.access_denied", "目录引用不能派生 $requestedAccess 文件引用")
        }
        val relative = input("relative_path") as? String
            ?: throw RuntimeFailure("file.relative_path_type", "相对位置必须是文本")
        val segments = safeRelativeSegments(relative)
        val result = linkedMapOf<String, Any?>(
            "kind" to "file_ref",
            "platform" to platform,
            "source" to "derived_relative",
            "display_name" to segments.last(),
            "authorization_root_id" to authorizationRootId,
            "access" to listOf(requestedAccess),
        )
        if (platform == "windows") {
            val parentPath = directory["path"]?.toString().orEmpty()
            val authorizationRoot = directory["authorization_root"]?.toString().orEmpty()
            if (parentPath.isBlank() || authorizationRoot.isBlank()) {
                throw RuntimeFailure("file.invalid_reference", "Windows 目录引用缺少授权载荷")
            }
            // The input DirectoryReference has already been normalized by its
            // Windows host. The only appended names have just passed the
            // portable segment validator, so this remains lexical and pure.
            result["path"] = parentPath.trimEnd('\\', '/') + "\\" + segments.joinToString("\\")
            result["authorization_root"] = authorizationRoot
            return result
        }
        val privatePath = directory["private_path"]?.toString().orEmpty()
        val uri = directory["uri"]?.toString().orEmpty()
        if (privatePath.isBlank() && uri.isBlank()) {
            throw RuntimeFailure("file.invalid_reference", "Android 目录引用缺少私有路径或 SAF URI")
        }
        if (privatePath.isNotBlank()) result["private_path"] = privatePath
        if (uri.isNotBlank()) result["uri"] = uri
        val previous = (directory["relative_segments"] as? List<*>)?.map(Any?::toString).orEmpty()
        result["relative_segments"] = previous + segments
        return result
    }

    private fun safeRelativeSegments(relative: String): List<String> {
        if (relative.isEmpty() || relative.toByteArray(StandardCharsets.UTF_8).size > 4096) {
            throw RuntimeFailure("file.relative_path_invalid", "相对位置不能为空或超过 4096 字节")
        }
        if (relative.startsWith('/') || relative.startsWith('\\') || '\\' in relative) {
            throw RuntimeFailure("file.relative_path_invalid", "相对位置必须使用 /，且不能从根位置开始")
        }
        val segments = relative.split('/')
        if (segments.isEmpty() || segments.size > 128) {
            throw RuntimeFailure("file.relative_path_invalid", "相对位置层级无效或超过 128 层")
        }
        val reservedNames = setOf("CON", "PRN", "AUX", "NUL") +
            (1..9).flatMap { listOf("COM$it", "LPT$it") }
        val forbidden = setOf('<', '>', ':', '"', '\\', '|', '?', '*')
        for (segment in segments) {
            val invalid = segment.isEmpty() ||
                segment in setOf(".", "..") ||
                segment.lastOrNull() in setOf(' ', '.') ||
                segment.toByteArray(StandardCharsets.UTF_8).size > 255 ||
                segment.any { it.code < 32 || it.code == 127 } ||
                segment.any { it in forbidden } ||
                segment.substringBefore('.').uppercase(Locale.ROOT) in reservedNames
            if (invalid) {
                throw RuntimeFailure(
                    "file.relative_path_invalid",
                    "相对位置包含不安全的名称：${segment.ifEmpty { "<空>" }}",
                )
            }
        }
        return segments
    }

    private fun mergeMaps(old: Map<Any?, Any?>, other: Map<Any?, Any?>, policy: String): Map<Any?, Any?> {
        val overlap = old.keys.any { key -> other.keys.any { EcirValueEvaluator.equivalent(key, it) } }
        if (overlap && policy == "error") throw RuntimeFailure("runtime.map_duplicate_key", "字典合并遇到重复键")
        return LinkedHashMap<Any?, Any?>().apply {
            if (policy == "keep_old") {
                putAll(other)
                putAll(old)
            } else {
                putAll(old)
                putAll(other)
            }
        }
    }

    private fun locate(root: Any?, path: List<Any?>): Pair<Boolean, Any?> {
        var current = root
        for (part in path) {
            current = when (current) {
                is Map<*, *> -> if (part in current) current[part] else return false to null
                is List<*> -> {
                    val index = (part as? Number)?.toInt() ?: return false to null
                    current.getOrNull(index) ?: return false to null
                }
                else -> return false to null
            }
        }
        return true to current
    }

    private fun mutatePath(root: Any?, path: List<Any?>, value: Any?, delete: Boolean): Any? {
        val copy = deepCopy(root)
        if (path.isEmpty()) return if (delete) null else value
        val parentPath = path.dropLast(1)
        val (found, parent) = locate(copy, parentPath)
        if (!found) return null
        val key = path.last()
        when (parent) {
            is MutableMap<*, *> -> {
                @Suppress("UNCHECKED_CAST") val mutable = parent as MutableMap<Any?, Any?>
                if (delete) mutable.remove(key) else mutable[key] = deepCopy(value)
            }
            is MutableList<*> -> {
                @Suppress("UNCHECKED_CAST") val mutable = parent as MutableList<Any?>
                val index = (key as? Number)?.toInt() ?: return null
                if (index !in mutable.indices) return null
                if (delete) mutable.removeAt(index) else mutable[index] = deepCopy(value)
            }
            else -> return null
        }
        return copy
    }

    private fun validateSchema(value: Any?, schema: Map<String, Any?>, path: String) {
        val type = schema["type"]?.toString()
        val valid = when (type) {
            null -> true
            "null" -> value == null
            "boolean" -> value is Boolean
            "integer" -> value is Byte || value is Short || value is Int || value is Long
            "number" -> value is Number
            "string" -> value is String
            "array" -> value is List<*>
            "object" -> value is Map<*, *>
            else -> throw RuntimeFailure("runtime.json_schema_invalid", "JSON Schema 类型不受支持：$type")
        }
        if (!valid) throw RuntimeFailure("runtime.json_schema_invalid", "JSON 不符合 Schema，位置 $path：需要 $type")
        val enumValues = schema["enum"] as? List<*>
        if (enumValues != null && enumValues.none { EcirValueEvaluator.equivalent(it, value) }) {
            throw RuntimeFailure("runtime.json_schema_invalid", "JSON 不符合 Schema，位置 $path：不在枚举中")
        }
        if (value is Map<*, *>) {
            val required = (schema["required"] as? List<*>)?.map(Any?::toString).orEmpty()
            val missing = required.firstOrNull { it !in value }
            if (missing != null) throw RuntimeFailure("runtime.json_schema_invalid", "JSON 不符合 Schema，位置 $path：缺少 $missing")
            val properties = schema["properties"] as? Map<*, *> ?: emptyMap<Any?, Any?>()
            for ((key, childSchema) in properties) {
                if (key in value && childSchema is Map<*, *>) {
                    @Suppress("UNCHECKED_CAST")
                    validateSchema(value[key], childSchema as Map<String, Any?>, "$path.$key")
                }
            }
        }
        if (value is List<*>) {
            val itemSchema = schema["items"] as? Map<*, *>
            if (itemSchema != null) value.forEachIndexed { index, item ->
                @Suppress("UNCHECKED_CAST")
                validateSchema(item, itemSchema as Map<String, Any?>, "$path[$index]")
            }
        }
    }

    private fun list(value: Any?): List<Any?> = value as? List<Any?>
        ?: throw RuntimeFailure("runtime.argument_type", "纯值操作需要列表")

    private fun map(value: Any?): Map<Any?, Any?> = value as? Map<Any?, Any?>
        ?: throw RuntimeFailure("runtime.argument_type", "纯值操作需要字典")

    private fun stringMap(value: Any?): Map<String, Any?> {
        val source = value as? Map<*, *>
            ?: throw RuntimeFailure("runtime.argument_type", "纯值操作需要记录")
        return source.entries.associate { it.key.toString() to it.value }
    }

    private fun addNumbers(left: Any?, right: Any?): Any = numberResult(
        EcirValueEvaluator.decimal(left) + EcirValueEvaluator.decimal(right),
    )

    private fun index(items: List<*>, raw: Any?, allowEnd: Boolean): Int {
        val value = EcirValueEvaluator.number(raw).toInt()
        val upper = if (allowEnd) items.size else items.size - 1
        if (value !in 0..upper) throw RuntimeFailure("runtime.collection_index", "列表序号超出范围")
        return value
    }

    private fun sliceString(text: String, rawStart: Int, rawEnd: Int): String {
        val length = text.codePointCount(0, text.length)
        val start = normalizeSlice(rawStart, length)
        val end = normalizeSlice(rawEnd, length).coerceAtLeast(start)
        val startOffset = text.offsetByCodePoints(0, start)
        val endOffset = text.offsetByCodePoints(0, end)
        return text.substring(startOffset, endOffset)
    }

    private fun sliceList(items: List<Any?>, startValue: Any?, endValue: Any?): List<Any?> {
        val start = normalizeSlice(EcirValueEvaluator.number(startValue).toInt(), items.size)
        val end = normalizeSlice(EcirValueEvaluator.number(endValue).toInt(), items.size).coerceAtLeast(start)
        return items.subList(start, end).toList()
    }

    private fun normalizeSlice(value: Int, size: Int): Int =
        (if (value < 0) size + value else value).coerceIn(0, size)

    private fun compareAny(left: Any?, right: Any?): Int = EcirValueEvaluator.compareValues(left, right)

    private fun checkpoint(index: Int) {
        if (index % 256 == 0) control.checkpoint()
    }

    private fun budget(size: Int) {
        if (size > 100_000) throw RuntimeFailure("runtime.collection_budget", "集合超过单次纯值计算安全预算")
    }

    private fun deepCopy(value: Any?): Any? = when (value) {
        is Map<*, *> -> value.entries.associateTo(linkedMapOf()) { deepCopy(it.key) to deepCopy(it.value) }
        is List<*> -> value.map(::deepCopy).toMutableList()
        else -> value
    }
}
