package com.easycode.player.util

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import com.google.gson.JsonPrimitive
import java.nio.charset.StandardCharsets
import java.security.MessageDigest

object JsonSupport {
    val gson: Gson = GsonBuilder().disableHtmlEscaping().serializeNulls().create()

    fun parse(bytes: ByteArray): JsonElement =
        JsonParser.parseString(bytes.toString(StandardCharsets.UTF_8))

    fun parseObject(bytes: ByteArray, label: String): JsonObject {
        val value = try {
            parse(bytes)
        } catch (error: RuntimeException) {
            throw IllegalArgumentException("$label 不是有效 JSON", error)
        }
        require(value.isJsonObject) { "$label 必须是 JSON 对象" }
        return value.asJsonObject
    }

    fun canonicalBytes(value: JsonElement): ByteArray =
        canonical(value).toByteArray(StandardCharsets.UTF_8)

    fun canonical(value: JsonElement): String = buildString { appendCanonical(value) }

    private fun StringBuilder.appendCanonical(value: JsonElement) {
        when {
            value.isJsonNull -> append("null")
            value.isJsonPrimitive -> append(gson.toJson(value))
            value.isJsonArray -> {
                append('[')
                value.asJsonArray.forEachIndexed { index, item ->
                    if (index > 0) append(',')
                    appendCanonical(item)
                }
                append(']')
            }
            value.isJsonObject -> {
                append('{')
                value.asJsonObject.entrySet().sortedBy { it.key }.forEachIndexed { index, entry ->
                    if (index > 0) append(',')
                    append(gson.toJson(entry.key))
                    append(':')
                    appendCanonical(entry.value)
                }
                append('}')
            }
            else -> error("未知 JSON 类型")
        }
    }

    fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it) }

    fun JsonObject.string(name: String, default: String = ""): String =
        get(name)?.takeUnless { it.isJsonNull }?.asString ?: default

    fun JsonObject.int(name: String, default: Int = 0): Int =
        get(name)?.takeUnless { it.isJsonNull }?.asInt ?: default

    fun JsonObject.long(name: String, default: Long = 0L): Long =
        get(name)?.takeUnless { it.isJsonNull }?.asLong ?: default

    fun JsonObject.bool(name: String, default: Boolean = false): Boolean =
        get(name)?.takeUnless { it.isJsonNull }?.asBoolean ?: default

    fun JsonObject.obj(name: String): JsonObject =
        get(name)?.takeIf { it.isJsonObject }?.asJsonObject ?: JsonObject()

    fun JsonObject.array(name: String): JsonArray =
        get(name)?.takeIf { it.isJsonArray }?.asJsonArray ?: JsonArray()

    fun fromAny(value: Any?): JsonElement = when (value) {
        null -> JsonNull.INSTANCE
        is JsonElement -> value.deepCopy()
        is Boolean -> JsonPrimitive(value)
        is Number -> JsonPrimitive(value)
        is String -> JsonPrimitive(value)
        is Map<*, *> -> JsonObject().also { result ->
            value.forEach { (key, item) -> result.add(key.toString(), fromAny(item)) }
        }
        is Iterable<*> -> JsonArray().also { result -> value.forEach { result.add(fromAny(it)) } }
        else -> JsonPrimitive(value.toString())
    }

    fun toAny(value: JsonElement?): Any? = when {
        value == null || value.isJsonNull -> null
        value.isJsonArray -> value.asJsonArray.map(::toAny)
        value.isJsonObject -> value.asJsonObject.entrySet().associate { it.key to toAny(it.value) }
        value.isJsonPrimitive -> value.asJsonPrimitive.let {
            when {
                it.isBoolean -> it.asBoolean
                it.isString -> it.asString
                it.isNumber -> {
                    val decimal = it.asBigDecimal
                    if (decimal.scale() <= 0 && decimal >= Int.MIN_VALUE.toBigDecimal() && decimal <= Int.MAX_VALUE.toBigDecimal()) {
                        decimal.toInt()
                    } else if (
                        decimal.scale() <= 0 &&
                        decimal >= Long.MIN_VALUE.toBigDecimal() &&
                        decimal <= Long.MAX_VALUE.toBigDecimal()
                    ) {
                        decimal.toLong()
                    } else if (decimal.scale() <= 0) {
                        decimal
                    } else {
                        decimal.toDouble()
                    }
                }
                else -> it.asString
            }
        }
        else -> null
    }
}

fun JsonElement.deepCopyElement(): JsonElement = deepCopy()
