package com.easycode.player.profile

import com.easycode.player.bundle.BundleVerificationException
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.int
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import java.io.File
import java.time.Instant
import java.util.UUID

data class PlayerControlDestination(
    val productId: String,
    val releaseId: String,
    val profileId: String,
    val controlId: String,
    val actionId: String,
    val profileRevision: Int,
    val targetId: String,
) {
    init {
        require(productId.isNotBlank() && releaseId.isNotBlank())
        require(profileId.startsWith("profile_") && profileRevision >= 1)
        require(controlId.isNotBlank() && actionId.isNotBlank())
        require(
            targetId.isNotBlank() || actionId in setOf(
                "choose-resource", "choose-file-read", "choose-file-save", "choose-directory",
            ),
        )
    }

    fun toJson(): JsonObject = JsonObject().apply {
        addProperty("product_id", productId)
        addProperty("release_id", releaseId)
        addProperty("profile_id", profileId)
        addProperty("control_id", controlId)
        addProperty("action_id", actionId)
        addProperty("profile_revision", profileRevision)
        addProperty("target_id", targetId)
    }

    companion object {
        fun fromJson(value: JsonObject): PlayerControlDestination {
            val expected = setOf(
                "product_id", "release_id", "profile_id", "control_id", "action_id",
                "profile_revision", "target_id",
            )
            if (value.keySet() != expected) {
                throw ProfileException("AND-PROFILE-001", "PlayerControlDestination 字段不完整或包含未知字段")
            }
            return try {
                PlayerControlDestination(
                    productId = value.string("product_id"),
                    releaseId = value.string("release_id"),
                    profileId = value.string("profile_id"),
                    controlId = value.string("control_id"),
                    actionId = value.string("action_id"),
                    profileRevision = value.int("profile_revision"),
                    targetId = value.string("target_id"),
                )
            } catch (error: IllegalArgumentException) {
                throw ProfileException("AND-PROFILE-001", "PlayerControlDestination 稳定身份无效", error)
            }
        }
    }
}

data class PlayerProfile(
    val profileId: String,
    val name: String,
    val targetId: String,
    val values: JsonObject,
    val recording: JsonObject = defaultRecordingSettings(),
    val revision: Int,
    val createdAt: String,
    val updatedAt: String,
)

class ProfileException(val code: String, message: String, cause: Throwable? = null) :
    IllegalArgumentException("[$code] $message", cause)

class ProfileStore(private val context: android.content.Context) {
    private val lock = Any()

    fun list(bundle: VerifiedBundle): List<PlayerProfile> = synchronized(lock) {
        readDocument(bundle).obj("profiles").entrySet()
            .mapNotNull { it.value.takeIf(JsonElement::isJsonObject)?.asJsonObject }
            .map(::parseProfile)
            .sortedWith(compareBy<PlayerProfile> { it.name.lowercase() }.thenBy { it.profileId })
    }

    fun loadOrCreate(bundle: VerifiedBundle): PlayerProfile = synchronized(lock) {
        val document = readDocument(bundle)
        val profiles = document.obj("profiles")
        val existing = profiles.entrySet()
            .sortedBy { it.key }
            .firstOrNull()
            ?.value
            ?.takeIf { it.isJsonObject }
            ?.asJsonObject
        if (existing != null) return@synchronized parseProfile(existing)

        val profile = newProfile(bundle, "默认方案", defaultTargetId(bundle), defaultValues(bundle))
        validateProfile(bundle, profile)
        profiles.add(profile.profileId, profileToJson(profile))
        writeDocument(bundle, document)
        profile
    }

    fun create(
        bundle: VerifiedBundle,
        name: String,
        targetId: String,
        values: JsonObject? = null,
        recording: JsonObject? = null,
    ): PlayerProfile = synchronized(lock) {
        val document = readDocument(bundle)
        val profile = newProfile(
            bundle,
            name.trim().ifBlank { "新方案" },
            targetId.ifBlank { defaultTargetId(bundle) },
            values?.deepCopy() ?: defaultValues(bundle),
            recording,
        )
        validateProfile(bundle, profile)
        document.obj("profiles").add(profile.profileId, profileToJson(profile))
        writeDocument(bundle, document)
        profile
    }

    fun delete(bundle: VerifiedBundle, profileId: String): PlayerProfile? = synchronized(lock) {
        val document = readDocument(bundle)
        val profiles = document.obj("profiles")
        if (!profiles.has(profileId)) throw ProfileException("AND-PROFILE-002", "配置方案不存在：$profileId")
        profiles.remove(profileId)
        var fallback: PlayerProfile? = profiles.entrySet().firstOrNull()
            ?.value?.takeIf(JsonElement::isJsonObject)?.asJsonObject?.let(::parseProfile)
        if (fallback == null) {
            fallback = newProfile(bundle, "默认方案", defaultTargetId(bundle), defaultValues(bundle))
            validateProfile(bundle, fallback)
            profiles.add(fallback.profileId, profileToJson(fallback))
        }
        writeDocument(bundle, document)
        fallback
    }

    fun reload(bundle: VerifiedBundle, profileId: String): PlayerProfile = synchronized(lock) {
        val raw = readDocument(bundle).obj("profiles").get(profileId)
            ?.takeIf { it.isJsonObject }
            ?.asJsonObject
            ?: throw ProfileException("AND-PROFILE-002", "配置方案不存在：$profileId")
        parseProfile(raw)
    }

    fun save(
        bundle: VerifiedBundle,
        profileId: String,
        expectedRevision: Int,
        name: String,
        targetId: String,
        values: JsonObject,
        recording: JsonObject? = null,
    ): PlayerProfile = synchronized(lock) {
        val document = readDocument(bundle)
        val profiles = document.obj("profiles")
        val previous = profiles.get(profileId)?.takeIf { it.isJsonObject }?.asJsonObject
            ?: throw ProfileException("AND-PROFILE-002", "配置方案不存在：$profileId")
        val current = parseProfile(previous)
        if (current.revision != expectedRevision) {
            throw ProfileException("AND-PROFILE-003", "配置方案 revision 已过期，请重新载入")
        }
        val cleanName = name.trim()
        if (cleanName.isBlank() || cleanName.length > 80) {
            throw ProfileException("AND-PROFILE-004", "配置方案名称必须为 1-80 个字符")
        }
        val nextRevision = current.revision + 1
        val updated = current.copy(
            name = cleanName,
            targetId = targetId,
            values = values.deepCopy(),
            recording = if (recording == null) {
                normalizeRecordingSettings(current.recording, nextRevision)
            } else {
                normalizeRecordingSettings(
                    recording,
                    nextRevision,
                    confirmed = recording.get("confirm_current_revision")?.asBoolean ?: false,
                )
            },
            revision = nextRevision,
            updatedAt = Instant.now().toString(),
        )
        validateProfile(bundle, updated)
        profiles.add(profileId, profileToJson(updated))
        writeDocument(bundle, document)
        updated
    }

    fun commitValue(
        bundle: VerifiedBundle,
        destination: PlayerControlDestination,
        value: JsonElement,
    ): PlayerProfile = synchronized(lock) {
        validateDestination(bundle, destination)
        val document = readDocument(bundle)
        val profiles = document.obj("profiles")
        val raw = profiles.get(destination.profileId)?.takeIf { it.isJsonObject }?.asJsonObject
            ?: throw ProfileException("AND-PROFILE-002", "终端字段动作必须绑定已保存配置方案")
        val current = parseProfile(raw)
        if (current.revision != destination.profileRevision) {
            throw ProfileException("AND-PROFILE-003", "确认时配置方案 revision 已过期")
        }
        if (current.targetId != destination.targetId) {
            throw ProfileException("AND-PROFILE-005", "Capture 目标与已保存配置方案不一致")
        }
        val updatedValues = current.values.deepCopy()
        updatedValues.add(destination.controlId, value.deepCopy())
        val updated = current.copy(
            values = updatedValues,
            revision = current.revision + 1,
            updatedAt = Instant.now().toString(),
        )
        validateProfile(bundle, updated)
        profiles.add(updated.profileId, profileToJson(updated))
        writeDocument(bundle, document)
        updated
    }

    fun privateImageFile(
        bundle: VerifiedBundle,
        destination: PlayerControlDestination,
        digest: String,
    ): File {
        require(digest.matches(Regex("[0-9a-f]{64}")))
        return File(
            dataRoot(bundle),
            "profiles/${destination.profileId}/images/$digest.png",
        )
    }

    fun dataRoot(bundle: VerifiedBundle): File = File(
        context.filesDir,
        "player-data/${JsonSupport.sha256(bundle.productId.toByteArray())}",
    ).apply { mkdirs() }

    fun validateDestination(bundle: VerifiedBundle, destination: PlayerControlDestination): JsonObject {
        if (destination.productId != bundle.productId || destination.releaseId != bundle.releaseId) {
            throw ProfileException("AND-PROFILE-006", "PlayerControlDestination 产品或发布身份已过期")
        }
        val current = reload(bundle, destination.profileId)
        if (current.revision != destination.profileRevision || current.targetId != destination.targetId) {
            throw ProfileException("AND-PROFILE-003", "PlayerControlDestination 方案 revision 或目标已过期")
        }
        val control = findControl(bundle, destination.controlId)
        val actions = control.array("terminal_actions").mapNotNull { action ->
            action.takeIf { it.isJsonObject }?.asJsonObject
        }
        val published = actions.firstOrNull {
            it.string("action_id") == destination.actionId &&
                it.array("platforms").any { platform -> platform.asString == "android_local" }
        } ?: throw ProfileException("AND-PROFILE-007", "开发者未为当前字段发布此 Android 动作")
        if (published.string("action_id").isBlank()) {
            throw ProfileException("AND-PROFILE-007", "Player 字段动作无效")
        }
        return control
    }

    private fun validateProfile(bundle: VerifiedBundle, profile: PlayerProfile) {
        if (!profile.profileId.startsWith("profile_") || profile.revision < 1) {
            throw ProfileException("AND-PROFILE-008", "配置方案稳定 ID 或 revision 无效")
        }
        val targets = bundle.project.array("targets").mapNotNull { item ->
            item.takeIf { it.isJsonObject }?.asJsonObject?.string("target_id")
        }
        if (targets.isNotEmpty() && profile.targetId !in targets) {
            throw ProfileException("AND-PROFILE-009", "配置方案目标不在签名目标闭包中")
        }
        val controls = buildMap {
            for (page in bundle.form.array("pages")) {
                if (!page.isJsonObject) continue
                for (control in page.asJsonObject.array("controls")) {
                    if (control.isJsonObject) put(control.asJsonObject.string("control_id"), control.asJsonObject)
                }
            }
        }
        val unknown = profile.values.keySet() - controls.keys
        if (unknown.isNotEmpty()) {
            throw ProfileException("AND-PROFILE-010", "配置方案包含未发布控件：${unknown.sorted().first()}")
        }
        // A saved scheme may still be incomplete so that a required capture or
        // SAF field can obtain a stable profile/revision destination.  Run
        // preflight, not persistence, rejects missing required values.
        val encoded = JsonSupport.canonicalBytes(profile.values)
        if (encoded.size > 1024 * 1024) {
            throw ProfileException("AND-PROFILE-012", "配置方案超过 1MB 限制")
        }
    }

    private fun defaultTargetId(bundle: VerifiedBundle): String = bundle.project.string("default_target_id").ifBlank {
        bundle.project.array("targets").firstOrNull()
            ?.takeIf { it.isJsonObject }
            ?.asJsonObject
            ?.string("target_id")
            .orEmpty()
    }

    private fun defaultValues(bundle: VerifiedBundle): JsonObject = JsonObject().apply {
        for (page in bundle.form.array("pages")) {
            if (!page.isJsonObject) continue
            for (control in page.asJsonObject.array("controls")) {
                if (!control.isJsonObject) continue
                val item = control.asJsonObject
                if (item.string("type") != "button" && item.has("default")) {
                    add(item.string("control_id"), item.get("default").deepCopy())
                }
            }
        }
    }

    private fun newProfile(
        bundle: VerifiedBundle,
        name: String,
        targetId: String,
        values: JsonObject,
        recording: JsonObject? = null,
    ): PlayerProfile {
        val now = Instant.now().toString()
        return PlayerProfile(
            profileId = "profile_${UUID.randomUUID().toString().replace("-", "")}",
            name = name,
            targetId = targetId,
            values = values,
            recording = normalizeRecordingSettings(
                recording,
                1,
                confirmed = recording?.get("confirm_current_revision")?.asBoolean ?: false,
            ),
            revision = 1,
            createdAt = now,
            updatedAt = now,
        )
    }

    fun toJson(profile: PlayerProfile): JsonObject = profileToJson(profile).apply {
        add("image_overrides", JsonObject())
    }

    private fun findControl(bundle: VerifiedBundle, controlId: String): JsonObject {
        for (page in bundle.form.array("pages")) {
            if (!page.isJsonObject) continue
            for (control in page.asJsonObject.array("controls")) {
                if (control.isJsonObject && control.asJsonObject.string("control_id") == controlId) {
                    return control.asJsonObject
                }
            }
        }
        throw ProfileException("AND-PROFILE-013", "Player 字段不存在：$controlId")
    }

    private fun documentFile(bundle: VerifiedBundle) = File(dataRoot(bundle), "profiles.json")

    private fun readDocument(bundle: VerifiedBundle): JsonObject {
        val path = documentFile(bundle)
        if (!path.isFile) return JsonObject().apply {
            addProperty("schema_version", 3)
            add("profiles", JsonObject())
        }
        val value = try {
            JsonSupport.parseObject(path.readBytes(), "配置方案文档")
        } catch (error: Exception) {
            throw ProfileException("AND-PROFILE-014", "配置方案文档损坏", error)
        }
        if (value.int("schema_version") != 3 || value.get("profiles")?.isJsonObject != true) {
            throw ProfileException("AND-PROFILE-014", "配置方案文档版本或结构无效")
        }
        return value
    }

    private fun writeDocument(bundle: VerifiedBundle, document: JsonObject) {
        AtomicFiles.write(documentFile(bundle), JsonSupport.canonicalBytes(document))
    }

    private fun parseProfile(raw: JsonObject): PlayerProfile {
        return PlayerProfile(
            profileId = raw.string("profile_id"),
            name = raw.string("name"),
            targetId = raw.string("target_id"),
            values = raw.obj("values").deepCopy(),
            recording = normalizeRecordingSettings(
                raw.get("recording")?.takeIf { it.isJsonObject }?.asJsonObject,
                raw.int("revision"),
            ),
            revision = raw.int("revision"),
            createdAt = raw.string("created_at"),
            updatedAt = raw.string("updated_at"),
        ).also {
            if (
                !it.profileId.startsWith("profile_") || it.name.isBlank() || it.revision < 1 ||
                it.createdAt.isBlank() || it.updatedAt.isBlank()
            ) {
                throw ProfileException("AND-PROFILE-014", "配置方案记录结构无效")
            }
        }
    }

    private fun profileToJson(profile: PlayerProfile): JsonObject = JsonObject().apply {
        addProperty("profile_id", profile.profileId)
        addProperty("name", profile.name)
        addProperty("target_id", profile.targetId)
        add("values", profile.values.deepCopy())
        add("recording", profile.recording.deepCopy())
        addProperty("revision", profile.revision)
        addProperty("created_at", profile.createdAt)
        addProperty("updated_at", profile.updatedAt)
    }
}
