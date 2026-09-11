package com.easycode.player.update

import android.content.Context
import android.os.Build
import android.content.pm.PackageInstaller
import com.easycode.player.BuildConfig
import com.easycode.player.bundle.ContentPackageRepository
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.runtime.RuntimeController
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.int
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import java.io.File
import java.io.RandomAccessFile
import java.net.HttpURLConnection
import java.net.URI
import java.net.URL
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.security.SecureRandom
import java.time.Instant
import com.easycode.player.util.Base64Codec

internal data class AndroidUpdateResponse(val status: Int, val bytes: ByteArray)

internal interface AndroidUpdateTransport {
    fun get(path: String, maximumBytes: Long): AndroidUpdateResponse
    fun download(path: String, destination: File, expectedBytes: Long, expectedSha256: String): Long
}

private class HttpsAndroidUpdateTransport(private val baseUrl: String) : AndroidUpdateTransport {
    private val base = URI(baseUrl.trim().trimEnd('/') + "/").also {
        if (it.scheme != "https" || it.userInfo != null || it.host.isNullOrBlank()) {
            throw AndroidUpdateFailure("UPD-SOURCE-001", "更新源必须是无凭据的 HTTPS 地址")
        }
    }

    override fun get(path: String, maximumBytes: Long): AndroidUpdateResponse {
        val connection = connection(path)
        return try {
            val status = connection.responseCode
            if (status in 300..399) throw AndroidUpdateFailure("UPD-SOURCE-001", "更新源重定向未经过签名根授权")
            val stream = if (status >= 400) connection.errorStream else connection.inputStream
            val bytes = if (stream == null) ByteArray(0) else stream.use { input ->
                val output = java.io.ByteArrayOutputStream()
                val buffer = ByteArray(64 * 1024)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    if (output.size().toLong() + count > maximumBytes) throw AndroidUpdateFailure("UPD-LIMIT-001", "更新响应超过签名大小上限")
                    output.write(buffer, 0, count)
                }
                output.toByteArray()
            }
            AndroidUpdateResponse(status, bytes)
        } catch (error: AndroidUpdateFailure) {
            throw error
        } catch (error: Exception) {
            throw AndroidUpdateFailure("UPD-NET-001", "更新源不可达：${error.message}", error)
        } finally {
            connection.disconnect()
        }
    }

    override fun download(path: String, destination: File, expectedBytes: Long, expectedSha256: String): Long {
        if (expectedBytes < 1 || !Regex("^[0-9a-f]{64}$").matches(expectedSha256)) {
            throw AndroidUpdateFailure("UPD-DOWNLOAD-001", "签名下载约束无效")
        }
        val parent = destination.parentFile
            ?: throw AndroidUpdateFailure("UPD-DOWNLOAD-001", "更新暂存路径没有父目录")
        parent.mkdirs()
        val partial = File(parent, ".${destination.name}.part")
        if (partial.length() > expectedBytes) partial.delete()
        var offset = partial.takeIf(File::isFile)?.length() ?: 0L
        if (parent.usableSpace < (expectedBytes - offset) + MIN_FREE_SPACE_BYTES) {
            throw AndroidUpdateFailure("UPD-SPACE-001", "存储空间不足，无法安全暂存更新")
        }
        val connection = connection(path).apply {
            if (offset > 0) setRequestProperty("Range", "bytes=$offset-")
            setRequestProperty("Accept", "application/octet-stream")
        }
        try {
            val status = connection.responseCode
            if (status in 300..399) throw AndroidUpdateFailure("UPD-SOURCE-001", "更新源重定向未经过签名根授权")
            if (status == 416 && offset == expectedBytes) {
                // A previous request wrote the complete payload but died before verification.
            } else {
                if (status !in setOf(200, 206)) throw AndroidUpdateFailure("UPD-NET-HTTP", "更新下载返回 $status")
                if (status == 206) {
                    val contentRange = connection.getHeaderField("Content-Range").orEmpty()
                    if (!contentRange.startsWith("bytes $offset-")) {
                        throw AndroidUpdateFailure("UPD-RANGE-001", "更新源返回了不一致的断点范围")
                    }
                } else if (offset > 0) {
                    // The server does not support Range. Restart safely instead of appending duplicates.
                    partial.delete()
                    offset = 0
                }
                connection.inputStream.use { input ->
                    RandomAccessFile(partial, "rw").use { output ->
                        output.seek(offset)
                        val buffer = ByteArray(128 * 1024)
                        var written = offset
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            written += count
                            if (written > expectedBytes) throw AndroidUpdateFailure("UPD-LIMIT-001", "更新产物超过签名大小")
                            output.write(buffer, 0, count)
                        }
                        output.fd.sync()
                    }
                }
            }
            if (partial.length() != expectedBytes || sha256(partial) != expectedSha256) {
                partial.delete()
                throw AndroidUpdateFailure("UPD-HASH-001", "更新产物大小或哈希不一致")
            }
            try {
                Files.move(partial.toPath(), destination.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            } catch (_: Exception) {
                Files.move(partial.toPath(), destination.toPath(), StandardCopyOption.REPLACE_EXISTING)
            }
            return offset
        } catch (error: AndroidUpdateFailure) {
            throw error
        } catch (error: Exception) {
            throw AndroidUpdateFailure("UPD-NET-001", "更新下载中断，可在下次继续：${error.message}", error)
        } finally {
            connection.disconnect()
        }
    }

    private fun connection(path: String): HttpURLConnection {
        val clean = path.replace('\\', '/')
        if (clean.startsWith('/') || clean.split('/').contains("..")) throw AndroidUpdateFailure("UPD-SOURCE-001", "更新源路径越界")
        val target = base.resolve(clean)
        if (target.scheme != base.scheme || target.authority != base.authority) throw AndroidUpdateFailure("UPD-SOURCE-001", "更新请求越过固定源边界")
        return (URL(target.toASCIIString()).openConnection() as HttpURLConnection).apply {
            connectTimeout = 15_000
            readTimeout = 30_000
            instanceFollowRedirects = false
            requestMethod = "GET"
            setRequestProperty("Accept", "application/json, application/octet-stream;q=0.9")
        }
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(128 * 1024)
            while (true) {
                val count = input.read(buffer)
                if (count < 0) break
                digest.update(buffer, 0, count)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    companion object { private const val MIN_FREE_SPACE_BYTES = 32L * 1024 * 1024 }
}

/** Android terminal update state. No config means no identity, worker or request. */
class AndroidUpdateManager(
    private val context: Context,
    private val packages: ContentPackageRepository,
    private val runtime: RuntimeController,
) {
    private val lock = Any()
    private var bundle: VerifiedBundle? = null
    private var domains = linkedMapOf<String, Domain>()
    private val apkInstaller = AndroidApkInstaller(context)

    fun configure(value: VerifiedBundle) = synchronized(lock) {
        bundle = value
        domains = linkedMapOf()
        if (!value.hasEntry("update/config.json")) {
            AndroidUpdateJobService.schedule(context, false)
            return@synchronized
        }
        val config = JsonSupport.parseObject(value.readEntry("update/config.json"), "更新配置")
        if (config.int("schema_version") != 1 || config.string("protocol") != "easycode-update-feed" || config.bool("telemetry", true)) {
            throw AndroidUpdateFailure("UPD-CONFIG-005", "Player 更新闭包无效")
        }
        config.obj("domains").entrySet().sortedBy { it.key }.forEach { (id, raw) ->
            if (id !in setOf("project_content", "player_application") || !raw.isJsonObject) {
                throw AndroidUpdateFailure("UPD-CONFIG-005", "Android 更新产品域无效")
            }
            val domain = Domain(id, raw.asJsonObject, value)
            if (id == "player_application" && !BuildConfig.APPLICATION_UPDATES_ENABLED) {
                throw AndroidUpdateFailure("UPD-CONFIG-006", "项目启用了 Player 应用更新，但 APK 未声明系统安装能力")
            }
            if (domains.values.any { it.productId == domain.productId }) throw AndroidUpdateFailure("UPD-CONFIG-005", "更新产品身份不能跨域复用")
            domains[id] = domain
        }
        AndroidUpdateJobService.schedule(context, domains.values.any { it.needsBackgroundCheck() })
    }

    fun status(): JsonObject = synchronized(lock) { JsonObject().apply {
        addProperty("enabled", domains.isNotEmpty())
        add("domains", JsonObject().apply { domains.forEach { (id, domain) -> add(id, domain.status()) } })
        addProperty("telemetry", false)
        addProperty("task_execution_requires_network", false)
    } }

    fun check(domainId: String, policyOnly: Boolean = false): JsonObject = domain(domainId).check(policyOnly)
    fun download(domainId: String): JsonObject = domain(domainId).download()
    fun apply(domainId: String): JsonObject = domain(domainId).apply()
    fun savePreferences(domainId: String, raw: JsonObject): JsonObject {
        val result = domain(domainId).savePreferences(raw)
        synchronized(lock) {
            AndroidUpdateJobService.schedule(context, domains.values.any { it.needsBackgroundCheck() })
        }
        return result
    }
    fun groupCode(domainId: String): JsonObject = domain(domainId).groupCode(false)
    fun resetGroupCode(domainId: String): JsonObject = domain(domainId).groupCode(true)

    fun onPackageInstallResult(domainId: String, releaseId: String, releaseSequence: Int, status: Int, message: String) =
        runCatching { domain(domainId).onPackageInstallResult(releaseId, releaseSequence, status, message) }

    fun assertTaskStartAllowed() = synchronized(lock) {
        domains.values.forEach { it.assertTaskStartAllowed() }
    }

    /** Runs only from the OS network-constrained update job. */
    fun automaticPass(): JsonObject = synchronized(lock) {
        JsonObject().apply {
            domains.forEach { (id, domain) ->
                add(id, runCatching { domain.automaticPass() }.getOrElse { error ->
                    JsonObject().apply {
                        addProperty("code", (error as? AndroidUpdateFailure)?.errorId ?: "UPD-CHECK-001")
                        addProperty("message", error.message ?: "后台更新失败")
                    }
                })
            }
        }
    }

    private fun domain(id: String): Domain = synchronized(lock) {
        domains[id] ?: throw AndroidUpdateFailure("UPD-DISABLED-001", "该更新产品域未启用")
    }

    private inner class Domain(
        val id: String,
        private val config: JsonObject,
        initialBundle: VerifiedBundle,
    ) {
        val productId = config.string("product_id").also { if (it.isBlank()) throw AndroidUpdateFailure("UPD-CONFIG-005", "更新产品身份为空") }
        private val channel = config.string("channel").also { if (it !in setOf("stable", "test")) throw AndroidUpdateFailure("UPD-CONFIG-005", "更新通道无效") }
        private val requiredPolicyCapability = config.bool("required_policy_capability")
        private val rootDir = File(context.noBackupFilesDir, "updates-v1/${JsonSupport.sha256("$productId:$id".toByteArray())}")
        private val stateFile = File(rootDir, "state.json")
        private val trustFile = File(rootDir, "trust.json")
        private val groupFile = File(rootDir, "group-code.txt")
        private val downloadDir = File(context.cacheDir, "updates-v1/${JsonSupport.sha256("$productId:$id".toByteArray())}")
        private val transport: AndroidUpdateTransport
        private var state: JsonObject
        private var trust: JsonObject

        init {
            val feed = config.string("feed_base_url")
            transport = HttpsAndroidUpdateTransport(feed)
            val pinned = config.obj("pinned_root")
            val verified = AndroidUpdateProtocol.initialRoot(pinned, productId)
            if (verified.array("mirrors").size() > 0 && verified.array("mirrors").none { it.asString.trimEnd('/') == feed.trimEnd('/') }) {
                throw AndroidUpdateFailure("UPD-SOURCE-002", "更新地址不在签名根允许范围内")
            }
            trust = load(trustFile) ?: JsonObject().apply {
                add("root", pinned.deepCopy())
                add("highest_versions", JsonObject().apply { addProperty("root", verified.int("version")) })
                add("role_hashes", JsonObject())
                addProperty("highest_release_sequence", 0)
                add("rollout_policies", JsonObject())
                add("last_required_policy", JsonNull.INSTANCE)
                addProperty("last_trusted_time", Instant.now().toString())
            }
            state = load(stateFile) ?: JsonObject().apply {
                addProperty("schema_version", 1)
                addProperty("state", "idle")
                addProperty("current_release_id", if (id == "project_content") initialBundle.releaseId else "android-app-${BuildConfig.VERSION_CODE}")
                addProperty("current_release_sequence", 0)
                add("selected_release", JsonNull.INSTANCE)
                add("selected_artifact", JsonNull.INSTANCE)
                addProperty("download_path", "")
                add("last_error", JsonNull.INSTANCE)
                addProperty("last_checked_at", "")
                add("preferences", preferences(config.obj("initial_preferences")))
            }
            reconcileInstalledApplication()
            persist()
        }

        /**
         * PackageInstaller normally kills the old process while replacing the APK, so its
         * final callback is not a reliable place to persist the terminal state.  On every
         * bootstrap, reconcile the signed staged release with the version Android actually
         * installed.  We deliberately require both a selected signed release and artifact;
         * an unrelated sideload must not advance the repository rollback floor.
         */
        private fun reconcileInstalledApplication() {
            if (id != "player_application") return
            val release = state.get("selected_release")?.takeIf(JsonElement::isJsonObject)?.asJsonObject ?: return
            val artifact = state.get("selected_artifact")?.takeIf(JsonElement::isJsonObject)?.asJsonObject ?: return
            if (artifact.string("kind") != "android_apk") return
            if (BuildConfig.VERSION_CODE < artifact.int("android_version_code")) return
            state.addProperty("current_release_id", release.string("release_id"))
            state.addProperty("current_release_sequence", release.int("release_sequence"))
            state.add("selected_release", JsonNull.INSTANCE)
            state.add("selected_artifact", JsonNull.INSTANCE)
            state.addProperty("download_path", "")
            state.addProperty("state", "complete")
            state.add("last_error", JsonNull.INSTANCE)
        }

        fun status(): JsonObject = synchronized(lock) {
            val copy = state.deepCopy()
            copy.addProperty("enabled", true)
            copy.addProperty("automatic_checks", copy.obj("preferences").bool("automatic_check"))
            copy.addProperty("required_policy_capability", requiredPolicyCapability)
            val block = policyBlock()
            copy.addProperty("can_start_task", block == null)
            copy.add("policy_block", block ?: JsonNull.INSTANCE)
            copy
        }

        fun needsBackgroundCheck(): Boolean {
            val value = state.obj("preferences")
            return value.bool("automatic_check") || requiredPolicyCapability
        }

        fun automaticPass(): JsonObject = synchronized(lock) {
            val value = state.obj("preferences")
            val checkResult = when {
                value.bool("automatic_check") -> check(false)
                requiredPolicyCapability -> check(true)
                else -> return@synchronized JsonObject().apply { addProperty("skipped", true) }
            }
            if (!checkResult.bool("checked")) return@synchronized checkResult
            if (value.bool("automatic_download") && state.string("state") == "available") download()
            // Android application replacement always requires the visible system installer.
            // Background auto-apply therefore only crosses the atomic project-content boundary.
            if (value.bool("automatic_apply") && state.string("state") == "staged" && id == "project_content") apply()
            status()
        }

        fun check(policyOnly: Boolean): JsonObject = synchronized(lock) {
            if (policyOnly && !requiredPolicyCapability) return@synchronized result(false, false, "未启用强制策略能力")
            transition("checking")
            try {
                val now = trustedNow()
                var root = AndroidUpdateProtocol.initialRoot(trust.obj("root"), productId, now)
                while (true) {
                    val response = transport.get("metadata/${root.int("version") + 1}.root.json", MAX_METADATA_BYTES)
                    if (response.status == 404) break
                    requireOk(response, "信任根轮换")
                    val envelope = parse(response.bytes, "更新信任根")
                    root = AndroidUpdateProtocol.rotatedRoot(root, envelope, now)
                    trust.add("root", envelope)
                    trust.obj("highest_versions").addProperty("root", root.int("version"))
                    saveTrust()
                }
                val timestampBytes = fetch("metadata/timestamp.json", "timestamp")
                val timestamp = verifyRole(timestampBytes, root, "timestamp", now)
                val snapshotRecord = timestamp.obj("meta").obj("snapshot.json")
                val snapshotBytes = fetch("metadata/${snapshotRecord.int("version")}.snapshot.json", "snapshot")
                AndroidUpdateProtocol.verifyMetadata(snapshotBytes, snapshotRecord, "snapshot.json")
                val snapshot = verifyRole(snapshotBytes, root, "snapshot", now)
                val names = if (policyOnly) listOf("policy") else listOf("targets", "rollout", "policy")
                val signed = linkedMapOf<String, JsonObject>()
                names.forEach { name ->
                    val record = snapshot.obj("meta").obj("$name.json")
                    val bytes = fetch("metadata/${record.int("version")}.$name.json", name)
                    AndroidUpdateProtocol.verifyMetadata(bytes, record, "$name.json")
                    signed[name] = verifyRole(bytes, root, name, now)
                }
                acceptRequiredPolicy(signed.getValue("policy").get("required_policy"))
                state.addProperty("last_checked_at", now.toString())
                if (policyOnly) {
                    transition(if (state.string("download_path").isBlank()) "idle" else "staged")
                    return@synchronized result(true, false, "最低版本策略已验证")
                }
                val releases = AndroidUpdateProtocol.validateTargets(signed.getValue("targets"), productId, id)
                acceptReleaseFloor(releases)
                val policies = AndroidUpdateProtocol.validateRollout(signed.getValue("rollout"), productId, releases.map { it.string("release_id") }.toSet())
                acceptRolloutFloors(policies)
                val selected = select(releases, policies)
                if (selected == null) {
                    state.add("selected_release", JsonNull.INSTANCE); state.add("selected_artifact", JsonNull.INSTANCE); state.addProperty("download_path", "")
                    transition("idle")
                    return@synchronized result(true, false, "签名元数据验证完成，当前分组没有可用更新")
                }
                state.add("selected_release", selected.first)
                state.add("selected_artifact", selected.second)
                state.addProperty("download_path", "")
                transition("available")
                result(true, true, "发现可用更新")
            } catch (error: Exception) {
                failState(error)
                result(false, false, error.message ?: "更新检查失败")
            }
        }

        fun download(): JsonObject = synchronized(lock) {
            val release = state.get("selected_release")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
                ?: throw AndroidUpdateFailure("UPD-DOWNLOAD-001", "没有已验证的可下载更新")
            val artifact = state.get("selected_artifact")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
                ?: throw AndroidUpdateFailure("UPD-DOWNLOAD-001", "没有已验证的更新产物")
            transition("downloading")
            try {
                val expected = artifact.get("length").asLong
                downloadDir.mkdirs()
                val destination = File(downloadDir, "${release.string("release_id")}-${artifact.string("artifact_id")}.payload")
                val resumedFrom = transport.download(
                    artifact.string("path"), destination, expected, artifact.obj("hashes").string("sha256"),
                )
                state.addProperty("download_path", destination.absolutePath)
                transition("staged")
                JsonObject().apply {
                    addProperty("downloaded", true)
                    addProperty("resumed_from_bytes", resumedFrom)
                    addProperty("domain", id)
                    add("status", status())
                }
            } catch (error: Exception) {
                failState(error)
                throw error
            }
        }

        fun apply(): JsonObject = synchronized(lock) {
            val release = state.get("selected_release")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
                ?: throw AndroidUpdateFailure("UPD-APPLY-001", "没有待应用的更新")
            val artifact = state.get("selected_artifact")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
                ?: throw AndroidUpdateFailure("UPD-APPLY-001", "没有待应用的更新产物")
            val file = File(state.string("download_path"))
            if (!file.isFile) throw AndroidUpdateFailure("UPD-APPLY-001", "暂存更新文件已丢失")
            if (runtime.state().active) {
                transition("waiting_safe_point")
                return@synchronized JsonObject().apply { addProperty("domain", id); add("status", status()) }
            }
            if (id == "player_application") {
                transition("awaiting_platform_install")
                return@synchronized try {
                    val submitted = apkInstaller.begin(file, release, artifact)
                    JsonObject().apply {
                        addProperty("domain", id)
                        add("status", status())
                        add("platform_install", submitted)
                    }
                } catch (error: Exception) {
                    failState(error)
                    throw error
                }
            }
            transition("applying")
            try {
                val installed = packages.installContentUpdate(
                    file,
                    release.string("release_id"),
                    artifact.obj("hashes").string("sha256"),
                    artifact.string("application_fingerprint"),
                )
                bundle = installed
                state.addProperty("current_release_id", release.string("release_id"))
                state.addProperty("current_release_sequence", release.int("release_sequence"))
                state.add("selected_release", JsonNull.INSTANCE); state.add("selected_artifact", JsonNull.INSTANCE); state.addProperty("download_path", "")
                transition("complete")
                JsonObject().apply { addProperty("domain", id); add("status", status()); addProperty("content_applied", true) }
            } catch (error: Exception) {
                state.addProperty("state", "rolled_back")
                state.add("last_error", errorJson(error))
                saveState()
                JsonObject().apply { addProperty("domain", id); add("status", status()) }
            }
        }

        fun savePreferences(raw: JsonObject): JsonObject = synchronized(lock) {
            val value = preferences(raw)
            state.add("preferences", value)
            saveState()
            JsonObject().apply { addProperty("saved", true); addProperty("domain", id); add("preferences", value.deepCopy()) }
        }

        fun groupCode(reset: Boolean): JsonObject = synchronized(lock) {
            if (reset || !groupFile.isFile) {
                val bytes = ByteArray(24).also(SecureRandom()::nextBytes)
                AtomicFiles.write(
                    groupFile,
                    Base64Codec.encode(bytes, urlSafe = true, padded = false).toByteArray(Charsets.US_ASCII),
                )
            }
            JsonObject().apply { addProperty("domain", id); addProperty("group_code", groupFile.readText(Charsets.US_ASCII)); if (reset) addProperty("reset", true) }
        }

        fun assertTaskStartAllowed() {
            policyBlock()?.let { throw AndroidUpdateFailure(it.string("code"), it.string("message")) }
        }

        fun onPackageInstallResult(releaseId: String, releaseSequence: Int, installStatus: Int, message: String) = synchronized(lock) {
            val expected = state.get("selected_release")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
            if (expected == null || expected.string("release_id") != releaseId || expected.int("release_sequence") != releaseSequence) return@synchronized
            if (installStatus == PackageInstaller.STATUS_SUCCESS) {
                state.addProperty("current_release_id", releaseId)
                state.addProperty("current_release_sequence", releaseSequence)
                state.add("selected_release", JsonNull.INSTANCE)
                state.add("selected_artifact", JsonNull.INSTANCE)
                state.addProperty("download_path", "")
                transition("complete")
            } else {
                failState(AndroidUpdateFailure("UPD-PLATFORM-002", message.ifBlank { "Android 系统未完成 Player 安装" }))
            }
        }

        private fun verifyRole(bytes: ByteArray, root: JsonObject, role: String, now: Instant): JsonObject {
            val envelope = parse(bytes, role)
            val floors = trust.obj("highest_versions")
            val floor = floors.int(role)
            val signed = AndroidUpdateProtocol.role(envelope, root, role, productId, id, floor, now)
            val digest = JsonSupport.sha256(JsonSupport.canonicalBytes(signed))
            val prior = trust.obj("role_hashes").obj(role)
            if (prior.int("version") == signed.int("version") && prior.string("sha256").isNotBlank() && prior.string("sha256") != digest) {
                throw AndroidUpdateFailure("UPD-MIXMATCH-001", "同一 $role 元数据版本出现不同内容")
            }
            floors.addProperty(role, maxOf(floor, signed.int("version")))
            trust.obj("role_hashes").add(role, JsonObject().apply { addProperty("version", signed.int("version")); addProperty("sha256", digest) })
            advanceTrustedTime(signed.string("issued_at"))
            saveTrust()
            return signed
        }

        private fun select(releases: List<JsonObject>, policies: List<JsonObject>): Pair<JsonObject, JsonObject>? {
            val current = state.int("current_release_sequence")
            val byId = releases.associateBy { it.string("release_id") }
            val candidates = mutableListOf<JsonObject>()
            val required = trust.get("last_required_policy")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
            if (required != null && !required.bool("revoked") && applies(required)) byId[required.string("target_release_id")]?.let(candidates::add)
            val policy = policies.firstOrNull { it.string("channel") == channel }
            if (policy != null && AndroidUpdateProtocol.eligible(policy, productId, groupCode(false).string("group_code"))) {
                byId[policy.string("release_id")]?.takeUnless(candidates::contains)?.let(candidates::add)
            }
            candidates.sortByDescending { it.int("release_sequence") }
            val architecture = Build.SUPPORTED_ABIS.firstOrNull().orEmpty()
            for (release in candidates) {
                if (release.int("release_sequence") <= current) continue
                AndroidUpdateProtocol.compatibleArtifact(release, id, architecture, BuildConfig.VERSION_NAME, "6.0.0")
                    ?.takeIf { artifact ->
                        id != "project_content" || artifact.string("application_fingerprint") == bundle?.applicationFingerprint()
                    }
                    ?.let { return release.deepCopy() to it }
            }
            return null
        }

        private fun acceptReleaseFloor(releases: List<JsonObject>) {
            val highest = releases.maxOfOrNull { it.int("release_sequence") } ?: 0
            val previous = trust.int("highest_release_sequence")
            if (highest < previous) throw AndroidUpdateFailure("UPD-ROLLBACK-001", "新 targets 删除了已经信任的最高发布序号")
            trust.addProperty("highest_release_sequence", maxOf(highest, previous)); saveTrust()
        }

        private fun acceptRolloutFloors(policies: List<JsonObject>) {
            val previous = trust.obj("rollout_policies")
            policies.forEach { policy ->
                val key = policy.string("channel")
                val old = previous.get(key)?.takeIf(JsonElement::isJsonObject)?.asJsonObject
                if (old != null) {
                    val revision = policy.int("policy_revision")
                    if (revision < old.int("policy_revision")) throw AndroidUpdateFailure("UPD-ROLLBACK-001", "拒绝旧灰度策略")
                    if (revision == old.int("policy_revision") && JsonSupport.canonical(policy) != JsonSupport.canonical(old)) throw AndroidUpdateFailure("UPD-MIXMATCH-001", "同一灰度修订出现不同内容")
                    if (policy.string("release_id") == old.string("release_id") && policy.string("rollout_id") == old.string("rollout_id") && policy.int("percent_bps") < old.int("percent_bps")) {
                        throw AndroidUpdateFailure("UPD-ROLLOUT-002", "同一灰度发布比例不能缩小")
                    }
                }
                previous.add(key, policy.deepCopy())
            }
            saveTrust()
        }

        private fun acceptRequiredPolicy(raw: JsonElement?) {
            val candidate = AndroidUpdateProtocol.validateRequiredPolicy(raw) ?: return
            val previous = trust.get("last_required_policy")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
            if (previous != null) {
                if (candidate.int("policy_revision") < previous.int("policy_revision")) throw AndroidUpdateFailure("UPD-ROLLBACK-001", "拒绝旧最低版本策略")
                if (candidate.int("policy_revision") == previous.int("policy_revision") && JsonSupport.canonical(candidate) != JsonSupport.canonical(previous)) {
                    throw AndroidUpdateFailure("UPD-MIXMATCH-001", "同一最低版本策略修订出现不同内容")
                }
            }
            trust.add("last_required_policy", candidate); advanceTrustedTime(candidate.string("issued_at")); saveTrust()
        }

        private fun policyBlock(): JsonObject? {
            val policy = trust.get("last_required_policy")?.takeIf(JsonElement::isJsonObject)?.asJsonObject ?: return null
            if (policy.bool("revoked") || !applies(policy) || state.int("current_release_sequence") >= policy.int("minimum_release_sequence")) return null
            if (trustedNow().isBefore(Instant.parse(policy.string("grace_deadline")))) return null
            return JsonObject().apply {
                addProperty("code", "UPD-REQUIRED-001")
                addProperty("message", policy.string("reason", "当前版本低于作者要求的最低安全版本"))
                addProperty("target_release_id", policy.string("target_release_id"))
                addProperty("grace_deadline", policy.string("grace_deadline"))
            }
        }

        private fun applies(policy: JsonObject) = policy.array("platform_targets").any { it.asString == platformTarget() }
        private fun platformTarget() = "android:${Build.SUPPORTED_ABIS.firstOrNull().orEmpty()}"
        private fun trustedNow(): Instant = maxOf(Instant.now(), runCatching { Instant.parse(trust.string("last_trusted_time")) }.getOrDefault(Instant.EPOCH))
        private fun advanceTrustedTime(raw: String) {
            val issued = runCatching { Instant.parse(raw) }.getOrDefault(Instant.EPOCH)
            trust.addProperty("last_trusted_time", maxOf(trustedNow(), issued, Instant.now()).toString())
        }
        private fun fetch(path: String, label: String): ByteArray = transport.get(path, MAX_METADATA_BYTES).also { requireOk(it, label) }.bytes
        private fun requireOk(response: AndroidUpdateResponse, label: String) { if (response.status != 200) throw AndroidUpdateFailure("UPD-NET-HTTP", "$label 返回 ${response.status}") }
        private fun parse(bytes: ByteArray, label: String) = runCatching { JsonSupport.parseObject(bytes, label) }.getOrElse { throw AndroidUpdateFailure("UPD-META-001", "$label 不是有效 JSON", it) }
        private fun preferences(raw: JsonObject) = JsonObject().apply {
            addProperty("automatic_check", raw.bool("automatic_check", true)); addProperty("automatic_download", raw.bool("automatic_download")); addProperty("automatic_apply", raw.bool("automatic_apply"))
        }
        private fun result(checked: Boolean, available: Boolean, message: String) = JsonObject().apply {
            addProperty("state", state.string("state")); addProperty("checked", checked); addProperty("available", available); addProperty("message", message)
            state.get("selected_release")?.let { add("release", it.deepCopy()) }; state.get("selected_artifact")?.let { add("artifact", it.deepCopy()) }
        }
        private fun transition(value: String) { state.addProperty("state", value); state.add("last_error", JsonNull.INSTANCE); saveState() }
        private fun failState(error: Exception) { state.addProperty("state", "failed"); state.add("last_error", errorJson(error)); saveState() }
        private fun errorJson(error: Exception) = JsonObject().apply { addProperty("code", (error as? AndroidUpdateFailure)?.errorId ?: "UPD-CHECK-001"); addProperty("message", error.message ?: "更新失败") }
        private fun saveState() = AtomicFiles.write(stateFile, JsonSupport.canonicalBytes(state))
        private fun saveTrust() = AtomicFiles.write(trustFile, JsonSupport.canonicalBytes(trust))
        private fun persist() { saveTrust(); saveState() }
        private fun load(file: File): JsonObject? = if (!file.isFile) null else runCatching { JsonSupport.parseObject(file.readBytes(), file.name) }.getOrElse { throw AndroidUpdateFailure("UPD-STATE-001", "更新状态损坏：${file.name}", it) }
    }

    companion object { private const val MAX_METADATA_BYTES = 4L * 1024L * 1024L }
}
