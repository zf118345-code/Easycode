package com.easycode.player.bundle

import android.content.Context
import com.easycode.player.BuildConfig
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonObject
import java.io.File
import java.security.MessageDigest

class ContentPackageRepository(private val context: Context) {
    private val root = File(context.noBackupFilesDir, "content-v1")
    private val slotA = File(root, "slots/a.ecplayer")
    private val slotB = File(root, "slots/b.ecplayer")
    private val activeDocument = File(root, "active.json")
    private val embeddedStateDocument = File(root, "embedded-state.json")
    private val lock = Any()
    @Volatile private var cached: VerifiedBundle? = null

    data class BootstrapResult(
        val available: Boolean,
        val installedReleaseId: String? = null,
        val importedFromAdb: Boolean = false,
        val rejectedAdbInbox: Boolean = false,
        val reason: String = "",
    )

    fun bootstrap(importInbox: Boolean = true): BootstrapResult = synchronized(lock) {
        root.mkdirs()
        val bootstrap = context.assets.open("player/bootstrap.json").use { input ->
            JsonSupport.parseObject(input.readBytes(), "Android bootstrap")
        }
        val embedded = bootstrap.bool("embedded")
        var imported = false
        var rejectedInbox = false
        var inboxFailure = ""
        if (embedded) {
            val trustBytes = embeddedTrustRoot()
            val temporary = File(root, ".embedded.ecplayer")
            context.assets.open("player/project.ecplayer").use { input ->
                temporary.outputStream().use(input::copyTo)
            }
            try {
                val verified = BundleVerifier.verify(temporary, trustBytes, embeddedExtensionRegistry())
                val current = runCatching { openActiveLocked() }.getOrNull()
                val embeddedIdentity = JsonSupport.sha256(
                    "${BuildConfig.VERSION_CODE}\u0000${verified.releaseId}\u0000${verified.integritySha256}".toByteArray(),
                )
                val previousEmbeddedIdentity = runCatching {
                    JsonSupport.parseObject(embeddedStateDocument.readBytes(), "APK 内置内容状态").string("identity")
                }.getOrDefault("")
                if (shouldActivateEmbedded(current != null, previousEmbeddedIdentity, embeddedIdentity)) {
                    installVerifiedLocked(temporary, verified, trustBytes)
                } else if (current != null && current.releaseId == verified.releaseId && current.integritySha256 != verified.integritySha256) {
                    throw BundleVerificationException(
                        "AND-CONTENT-006",
                        "同一 release_id 对应不同签名内容；拒绝静默替换不可变发布",
                    )
                }
                AtomicFiles.write(embeddedStateDocument, JsonSupport.canonicalBytes(JsonObject().apply {
                    addProperty("schema_version", 1)
                    addProperty("identity", embeddedIdentity)
                    addProperty("app_version_code", BuildConfig.VERSION_CODE)
                    addProperty("release_id", verified.releaseId)
                    addProperty("integrity_sha256", verified.integritySha256)
                }))
            } finally {
                temporary.delete()
            }
        }
        if (importInbox && embedded) {
            try {
                imported = importAdbInboxLocked()
            } catch (error: Exception) {
                // A rejected development transfer must never replace or brick
                // the last verified A/B slot. Remove the untrusted inbox so a
                // valid offline Player can recover on this same launch.
                adbInboxPath().delete()
                rejectedInbox = true
                inboxFailure = error.message ?: "ADB 内容包校验失败"
            }
        }
        val loaded = runCatching { openActiveLocked() }.getOrElse { error ->
            return@synchronized BootstrapResult(
                available = false,
                reason = error.message ?: "Android Player 内容包不可用",
            )
        }
        BootstrapResult(
            available = true,
            installedReleaseId = loaded.releaseId,
            importedFromAdb = imported,
            rejectedAdbInbox = rejectedInbox,
            reason = inboxFailure,
        )
    }

    fun openActive(): VerifiedBundle = synchronized(lock) { openActiveLocked() }

    fun clearCache() = synchronized(lock) { cached = null }

    /**
     * Commit an already downloaded online content update through the same
     * signature verifier and inactive-slot path used by development import.
     * The caller's feed hash is checked again here so no unverified handoff
     * can cross the update/runtime boundary.
     */
    fun installContentUpdate(
        source: File,
        releaseId: String,
        artifactSha256: String,
        applicationFingerprint: String,
    ): VerifiedBundle = synchronized(lock) {
        require(source.isFile) { "暂存内容更新不存在" }
        val digest = MessageDigest.getInstance("SHA-256")
        source.inputStream().buffered().use { input ->
            val buffer = ByteArray(1024 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        val actualHash = digest.digest().joinToString("") { "%02x".format(it) }
        require(actualHash == artifactSha256) { "暂存内容更新哈希不一致" }
        val trustBytes = embeddedTrustRoot()
        val verified = BundleVerifier.verify(source, trustBytes, embeddedExtensionRegistry())
        require(verified.releaseId == releaseId) { "内容更新 release_id 与签名包不一致" }
        require(verified.applicationFingerprint() == applicationFingerprint) {
            "内容更新的 Runtime、权限或扩展闭包与签名元数据不一致"
        }
        val current = runCatching { openActiveLocked() }.getOrNull()
        if (current?.releaseId == verified.releaseId) {
            require(current.integritySha256 == verified.integritySha256) {
                "同一 release_id 对应不同签名内容"
            }
            return@synchronized current
        }
        installVerifiedLocked(source, verified, trustBytes)
        openActiveLocked()
    }

    fun adbInboxPath(): File = File(context.getExternalFilesDir("inbox"), "project.ecplayer")

    private fun openActiveLocked(): VerifiedBundle {
        cached?.let { return it }
        if (!activeDocument.isFile) {
            throw BundleVerificationException("AND-CONTENT-001", "APK 尚未安装签名 Player 内容包")
        }
        val active = JsonSupport.parseObject(activeDocument.readBytes(), "活动内容槽")
        val slot = when (active.string("slot")) {
            "a" -> slotA
            "b" -> slotB
            else -> throw BundleVerificationException("AND-CONTENT-002", "活动内容槽记录无效")
        }
        val verified = BundleVerifier.verify(slot, embeddedTrustRoot(), embeddedExtensionRegistry())
        if (active.string("release_id") != verified.releaseId) {
            throw BundleVerificationException("AND-CONTENT-003", "活动内容槽 release_id 不一致")
        }
        cached = verified
        return verified
    }

    private fun importAdbInboxLocked(): Boolean {
        val inbox = adbInboxPath()
        if (!inbox.isFile) return false
        val trustBytes = embeddedTrustRoot()
        val verified = BundleVerifier.verify(inbox, trustBytes, embeddedExtensionRegistry())
        val current = runCatching { openActiveLocked() }.getOrNull()
        if (current?.releaseId == verified.releaseId && current.integritySha256 != verified.integritySha256) {
            throw BundleVerificationException(
                "AND-CONTENT-006",
                "ADB 内容包复用了现有 release_id，但签名内容不同",
            )
        }
        if (current?.releaseId == verified.releaseId) {
            inbox.delete()
            return false
        }
        installVerifiedLocked(inbox, verified, trustBytes)
        inbox.delete()
        return true
    }

    private fun installVerifiedLocked(source: File, verified: VerifiedBundle, trustBytes: ByteArray) {
        val activeSlot = runCatching {
            JsonSupport.parseObject(activeDocument.readBytes(), "活动内容槽").string("slot")
        }.getOrDefault("")
        val nextSlotName = if (activeSlot == "a") "b" else "a"
        val nextSlot = if (nextSlotName == "a") slotA else slotB
        AtomicFiles.copy(source, nextSlot)
        val installed = BundleVerifier.verify(nextSlot, trustBytes, embeddedExtensionRegistry())
        if (
            installed.releaseId != verified.releaseId ||
            installed.integritySha256 != verified.integritySha256
        ) {
            nextSlot.delete()
            throw BundleVerificationException("AND-CONTENT-004", "内容槽复制后校验不一致")
        }
        val document = JsonObject().apply {
            addProperty("schema_version", 1)
            addProperty("slot", nextSlotName)
            addProperty("release_id", installed.releaseId)
            addProperty("integrity_sha256", installed.integritySha256)
        }
        AtomicFiles.write(activeDocument, JsonSupport.canonicalBytes(document))
        cached = installed
    }

    private fun embeddedTrustRoot(): ByteArray = try {
        context.assets.open("player/trust-root.json").use { it.readBytes() }
    } catch (error: Exception) {
        throw BundleVerificationException(
            "AND-CONTENT-005",
            "APK 未固定发布者信任根，不能加载外部 Player 包",
            error,
        )
    }

    private fun embeddedExtensionRegistry(): ByteArray = try {
        context.assets.open("player/extensions.json").use { it.readBytes() }
    } catch (error: Exception) {
        throw BundleVerificationException(
            "AND-EXT-001",
            "APK 未包含构建期扩展注册表",
            error,
        )
    }
}

internal fun shouldActivateEmbedded(hasCurrent: Boolean, previousIdentity: String, embeddedIdentity: String): Boolean =
    !hasCurrent || previousIdentity != embeddedIdentity
