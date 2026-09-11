package com.easycode.player.profile

import com.google.gson.JsonNull
import com.google.gson.JsonObject

private val RECORDING_FIELDS = setOf(
    "enabled", "strategy", "target_fps", "max_duration_ms", "max_session_bytes",
    "min_free_bytes", "confirmed_profile_revision", "confirm_current_revision",
)

internal fun normalizeRecordingSettings(
    value: JsonObject?,
    profileRevision: Int,
    confirmed: Boolean? = null,
): JsonObject {
    val raw = value ?: JsonObject()
    val unknown = raw.keySet() - RECORDING_FIELDS
    if (unknown.isNotEmpty()) {
        throw ProfileException("AND-PROFILE-015", "录制设置包含未知字段：${unknown.sorted().first()}")
    }
    val enabled = raw.get("enabled")?.takeUnless { it.isJsonNull }?.let {
        runCatching { it.asBoolean }.getOrElse {
            throw ProfileException("AND-PROFILE-015", "录制设置 enabled 无效")
        }
    } ?: false
    val strategy = raw.get("strategy")?.takeUnless { it.isJsonNull }?.asString ?: "changed_frames"
    if (strategy !in setOf("all_frames", "changed_frames", "diagnostic")) {
        throw ProfileException("AND-PROFILE-015", "录制策略无效")
    }

    fun decimal(name: String, default: Double, minimum: Double, maximum: Double): Double {
        val result = raw.get(name)?.takeUnless { it.isJsonNull }?.let {
            runCatching { it.asDouble }.getOrElse {
                throw ProfileException("AND-PROFILE-015", "录制设置 $name 无效")
            }
        } ?: default
        if (!result.isFinite() || result !in minimum..maximum) {
            throw ProfileException("AND-PROFILE-015", "录制设置 $name 超出范围")
        }
        return result
    }

    fun integer(name: String, default: Long, minimum: Long, maximum: Long): Long {
        val element = raw.get(name)?.takeUnless { it.isJsonNull } ?: return default
        val result = runCatching { element.asLong }.getOrElse {
            throw ProfileException("AND-PROFILE-015", "录制设置 $name 无效")
        }
        if (element.asString != result.toString() || result !in minimum..maximum) {
            throw ProfileException("AND-PROFILE-015", "录制设置 $name 超出范围")
        }
        return result
    }

    val persistedRevision = raw.get("confirmed_profile_revision")
        ?.takeUnless { it.isJsonNull }
        ?.let {
            val revision = runCatching { it.asInt }.getOrElse {
                throw ProfileException("AND-PROFILE-015", "录制确认 revision 无效")
            }
            if (revision < 1 || it.asString != revision.toString()) {
                throw ProfileException("AND-PROFILE-015", "录制确认 revision 无效")
            }
            revision
        }
    val explicitlyConfirmed = confirmed ?: (
        raw.get("confirm_current_revision")?.takeUnless { it.isJsonNull }?.asBoolean ?: false
    )
    if (enabled && confirmed != null && !explicitlyConfirmed) {
        throw ProfileException("AND-PROFILE-015", "启用录制前必须确认当前配置方案 revision")
    }
    val confirmedRevision = if (enabled && explicitlyConfirmed) profileRevision else persistedRevision

    return JsonObject().apply {
        addProperty("enabled", enabled)
        addProperty("strategy", strategy)
        addProperty("target_fps", decimal("target_fps", 15.0, 0.2, 60.0))
        addProperty("max_duration_ms", integer("max_duration_ms", 1_800_000, 1_000, 604_800_000))
        addProperty("max_session_bytes", integer("max_session_bytes", 2_147_483_648, 1_048_576, 1_000_000_000_000))
        addProperty("min_free_bytes", integer("min_free_bytes", 536_870_912, 67_108_864, 107_374_182_400))
        if (confirmedRevision == null) add("confirmed_profile_revision", JsonNull.INSTANCE)
        else addProperty("confirmed_profile_revision", confirmedRevision)
    }
}

internal fun defaultRecordingSettings(): JsonObject = normalizeRecordingSettings(null, 1)
