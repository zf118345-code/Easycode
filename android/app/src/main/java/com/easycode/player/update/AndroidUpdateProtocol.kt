package com.easycode.player.update

import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.int
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import java.math.BigInteger
import java.util.regex.Pattern
import java.time.Instant
import com.easycode.player.util.Base64Codec

class AndroidUpdateFailure(
    val errorId: String,
    message: String,
    cause: Throwable? = null,
) : IllegalStateException("[$errorId] $message", cause)

internal object AndroidUpdateProtocol {
    private val stableId = Regex("[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}")
    private val sha256 = Regex("[0-9a-f]{64}")
    private val roles = setOf("root", "timestamp", "snapshot", "targets", "rollout", "policy")

    fun initialRoot(envelope: JsonObject, productId: String, now: Instant = Instant.now()): JsonObject {
        val root = envelope.obj("signed")
        validateRoot(root, productId)
        val descriptor = root.obj("roles").obj("root")
        verifySignatures(envelope, root.obj("keys"), descriptor)
        if (!Instant.parse(root.string("expires")).isAfter(now)) fail("UPD-EXPIRED-001", "固定根元数据已过期")
        return root.deepCopy()
    }

    fun rotatedRoot(previous: JsonObject, envelope: JsonObject, now: Instant): JsonObject {
        validateRoot(previous, previous.string("product_id"))
        val candidate = envelope.obj("signed")
        validateRoot(candidate, previous.string("product_id"))
        if (candidate.int("version") != previous.int("version") + 1) {
            fail("UPD-ROLLBACK-001", "根元数据必须逐版本轮换")
        }
        verifySignatures(envelope, previous.obj("keys"), previous.obj("roles").obj("root"))
        verifySignatures(envelope, candidate.obj("keys"), candidate.obj("roles").obj("root"))
        if (!Instant.parse(candidate.string("expires")).isAfter(now)) fail("UPD-EXPIRED-001", "新根元数据已过期")
        return candidate.deepCopy()
    }

    fun role(
        envelope: JsonObject,
        root: JsonObject,
        role: String,
        productId: String,
        domain: String,
        minimumVersion: Int,
        now: Instant,
    ): JsonObject {
        if (role !in roles || role == "root") fail("UPD-META-001", "更新元数据角色无效")
        validateRoot(root, productId)
        verifySignatures(envelope, root.obj("keys"), root.obj("roles").obj(role))
        val signed = envelope.obj("signed")
        if (
            signed.string("_type") != role || signed.int("spec_version") != 1 ||
            signed.string("product_id") != productId || signed.string("domain") != domain
        ) fail("UPD-META-002", "$role 元数据身份不一致")
        if (signed.int("version") < maxOf(1, minimumVersion)) fail("UPD-ROLLBACK-001", "拒绝重放旧 $role 元数据")
        val issued = parseTime(signed.string("issued_at"), "$role.issued_at")
        val expires = parseTime(signed.string("expires"), "$role.expires")
        if (!expires.isAfter(now)) fail("UPD-EXPIRED-001", "$role 元数据已过期")
        if (issued.isAfter(now)) fail("UPD-FREEZE-001", "$role 元数据签发时间晚于可信时间")
        return signed.deepCopy()
    }

    fun verifyMetadata(bytes: ByteArray, record: JsonObject, name: String) {
        if (record.get("length")?.asLong != bytes.size.toLong()) fail("UPD-MIXMATCH-001", "$name 元数据长度不一致")
        val digest = record.obj("hashes").string("sha256")
        if (!sha256.matches(digest) || digest != JsonSupport.sha256(bytes)) fail("UPD-MIXMATCH-001", "$name 元数据哈希不一致")
    }

    fun validateTargets(value: JsonObject, productId: String, domain: String): List<JsonObject> {
        if (value.string("_type") != "targets" || value.string("product_id") != productId || value.string("domain") != domain) {
            fail("UPD-TARGET-001", "targets 元数据身份无效")
        }
        val releases = value.array("releases").map {
            if (!it.isJsonObject) fail("UPD-TARGET-001", "发布记录必须是对象")
            validateRelease(it.asJsonObject, domain)
        }
        val sequences = releases.map { it.int("release_sequence") }
        val ids = releases.map { it.string("release_id") }
        if (sequences != sequences.sorted() || sequences.toSet().size != sequences.size || ids.toSet().size != ids.size) {
            fail("UPD-TARGET-001", "发布序号或身份重复、乱序")
        }
        return releases
    }

    fun validateRollout(value: JsonObject, productId: String, releaseIds: Set<String>): List<JsonObject> {
        if (value.string("_type") != "rollout" || value.string("product_id") != productId) {
            fail("UPD-ROLLOUT-001", "灰度元数据身份无效")
        }
        return value.array("policies").map {
            if (!it.isJsonObject) fail("UPD-ROLLOUT-001", "灰度策略必须是对象")
            val policy = it.asJsonObject
            val releaseId = requireId(policy.string("release_id"), "release_id")
            requireId(policy.string("rollout_id"), "rollout_id")
            if (releaseId !in releaseIds || policy.string("channel") !in setOf("test", "stable")) {
                fail("UPD-ROLLOUT-001", "灰度策略引用或通道无效")
            }
            val percent = policy.int("percent_bps", -1)
            if (percent !in 0..10_000 || (policy.string("channel") == "test" && percent != 0)) {
                fail("UPD-ROLLOUT-001", "灰度比例无效")
            }
            if (policy.array("whitelist_hashes").any { !it.isJsonPrimitive || !sha256.matches(it.asString) }) {
                fail("UPD-ROLLOUT-001", "灰度白名单无效")
            }
            parseTime(policy.string("issued_at"), "rollout.issued_at")
            policy.deepCopy()
        }
    }

    fun eligible(policy: JsonObject, productId: String, groupCode: String): Boolean {
        if (policy.bool("paused")) return false
        val groupHash = JsonSupport.sha256((productId + groupCode).toByteArray(Charsets.UTF_8))
        if (policy.array("whitelist_hashes").any { it.asString == groupHash }) return true
        if (policy.string("channel") == "test") return false
        val digest = java.security.MessageDigest.getInstance("SHA-256")
            .digest((productId + policy.string("rollout_id") + groupCode).toByteArray(Charsets.UTF_8))
        return BigInteger(1, digest).mod(BigInteger.valueOf(10_000)).toInt() < policy.int("percent_bps")
    }

    fun validateRequiredPolicy(value: JsonElement?): JsonObject? {
        if (value == null || value.isJsonNull) return null
        if (!value.isJsonObject) fail("UPD-POLICY-001", "最低版本策略必须是对象")
        val policy = value.asJsonObject
        if (policy.int("policy_revision") < 1 || policy.int("minimum_release_sequence", -1) < 0) {
            fail("UPD-POLICY-001", "最低版本策略修订或序号无效")
        }
        if (policy.int("minimum_release_sequence") > 0) requireId(policy.string("target_release_id"), "target_release_id")
        val effective = parseTime(policy.string("effective_at"), "required.effective_at")
        val grace = parseTime(policy.string("grace_deadline"), "required.grace_deadline")
        if (grace.isBefore(effective)) fail("UPD-POLICY-001", "最低版本宽限期早于生效时间")
        parseTime(policy.string("issued_at"), "required.issued_at")
        if (policy.array("platform_targets").any { !it.isJsonPrimitive || !stableId.matches(it.asString) }) {
            fail("UPD-POLICY-001", "最低版本平台目标无效")
        }
        return policy.deepCopy()
    }

    fun compatibleArtifact(
        release: JsonObject,
        domain: String,
        architecture: String,
        runtimeVersion: String,
        ecirVersion: String,
    ): JsonObject? =
        release.array("artifacts").mapNotNull { it.takeIf(JsonElement::isJsonObject)?.asJsonObject }
            .map(::validateArtifact)
            .firstOrNull { artifact ->
                artifact.string("platform") == "android" && artifact.string("architecture") == architecture &&
                    versionInRange(runtimeVersion, artifact.string("runtime_min"), artifact.string("runtime_max")) &&
                    versionInRange(ecirVersion, artifact.string("ecir_min"), artifact.string("ecir_max")) &&
                    ((domain == "project_content" && artifact.string("kind") == "project_content") ||
                        (domain == "player_application" && artifact.string("kind") == "android_apk"))
            }?.deepCopy()

    fun versionInRange(current: String, minimum: String, maximum: String): Boolean {
        fun parts(value: String): List<Int> = value.split('.').map { item ->
            Pattern.compile("^(\\d+)").matcher(item).let { if (it.find()) it.group(1)?.toInt() ?: 0 else 0 }
        }.let { (it + listOf(0, 0, 0)).take(3) }
        val value = parts(current)
        fun compare(left: List<Int>, right: List<Int>): Int = left.indices.firstNotNullOfOrNull { index ->
            (left[index] - right[index]).takeIf { it != 0 }
        } ?: 0
        return compare(value, parts(minimum)) >= 0 && compare(value, parts(maximum)) <= 0
    }

    private fun validateRelease(release: JsonObject, domain: String): JsonObject {
        requireId(release.string("release_id"), "release_id")
        if (release.int("release_sequence") < 1 || !release.bool("immutable")) fail("UPD-TARGET-001", "发布序号或不可变声明无效")
        parseTime(release.string("created_at"), "release.created_at")
        val artifacts = release.array("artifacts")
        if (artifacts.size() == 0) fail("UPD-TARGET-001", "发布没有产物")
        val artifactIds = mutableSetOf<String>()
        artifacts.forEach { raw ->
            if (!raw.isJsonObject) fail("UPD-TARGET-001", "发布产物必须是对象")
            val artifact = validateArtifact(raw.asJsonObject)
            if (!artifactIds.add(artifact.string("artifact_id"))) fail("UPD-TARGET-001", "发布包含重复 artifact_id")
            val valid = (domain == "project_content" && artifact.string("kind") == "project_content") ||
                (domain == "player_application" && artifact.string("kind") == "android_apk")
            if (!valid) fail("UPD-TARGET-002", "发布产物与更新域混搭")
        }
        return release.deepCopy()
    }

    private fun validateArtifact(value: JsonObject): JsonObject {
        requireId(value.string("artifact_id"), "artifact_id")
        val kind = value.string("kind")
        val boundary = value.string("install_boundary")
        if (kind !in setOf("project_content", "android_apk") || value.string("platform") != "android") {
            fail("UPD-TARGET-001", "Android 更新产物类型无效")
        }
        if (boundary != if (kind == "project_content") "atomic_content_slot" else "android_package_installer") {
            fail("UPD-TARGET-001", "安装边界与产物类型不一致")
        }
        val path = value.string("path").replace('\\', '/')
        if (!path.startsWith("artifacts/") || path.startsWith('/') || path.split('/').contains("..")) {
            fail("UPD-TARGET-001", "更新产物路径越界")
        }
        if (value.get("length")?.asLong?.let { it > 0 } != true || !sha256.matches(value.obj("hashes").string("sha256"))) {
            fail("UPD-TARGET-001", "更新产物大小或哈希无效")
        }
        listOf("application_fingerprint", "content_fingerprint", "permissions_fingerprint").forEach {
            if (!sha256.matches(value.string(it))) fail("UPD-TARGET-001", "更新产物 $it 无效")
        }
        listOf("runtime_min", "runtime_max", "ecir_min", "ecir_max").forEach {
            if (value.string(it).isBlank()) fail("UPD-TARGET-001", "更新产物 $it 无效")
        }
        val abi = value.array("abi").map { it.asString }
        if (abi != abi.distinct() || abi.any { it.isBlank() }) fail("UPD-TARGET-001", "更新产物 ABI 无效")
        if (kind == "android_apk") {
            if (value.int("android_version_code") < 1 || !sha256.matches(value.string("android_certificate_sha256"))) {
                fail("UPD-TARGET-001", "Android APK 版本或证书指纹无效")
            }
        }
        return value
    }

    private fun validateRoot(root: JsonObject, productId: String) {
        if (
            root.string("_type") != "root" || root.int("spec_version") != 1 ||
            root.string("product_id") != productId || root.int("version") < 1 || !root.bool("consistent_snapshot")
        ) fail("UPD-ROOT-001", "更新根元数据无效")
        parseTime(root.string("expires"), "root.expires")
        val keys = root.obj("keys")
        val roleMap = root.obj("roles")
        if (roleMap.keySet() != roles) fail("UPD-ROOT-001", "更新根角色集合不完整")
        keys.entrySet().forEach { (id, raw) ->
            if (!raw.isJsonObject || keyId(raw.asJsonObject) != id) fail("UPD-ROOT-003", "更新根公钥指纹不一致")
        }
        roles.forEach { name ->
            val descriptor = roleMap.obj(name)
            val ids = descriptor.array("keyids").map { it.asString }
            if (ids.isEmpty() || ids.toSet().size != ids.size || ids.any { !keys.has(it) } || descriptor.int("threshold") !in 1..ids.size) {
                fail("UPD-ROOT-001", "更新根 $name 角色无效")
            }
        }
    }

    private fun verifySignatures(envelope: JsonObject, keys: JsonObject, descriptor: JsonObject) {
        val signed = envelope.get("signed")?.takeIf(JsonElement::isJsonObject)?.asJsonObject
            ?: fail("UPD-SIGN-002", "更新签名信封无效")
        val allowed = descriptor.array("keyids").map { it.asString }.toSet()
        val payload = JsonSupport.canonicalBytes(signed)
        val valid = mutableSetOf<String>()
        envelope.array("signatures").forEach { raw ->
            if (!raw.isJsonObject) return@forEach
            val item = raw.asJsonObject
            val id = item.string("keyid")
            if (id !in allowed || id in valid || !keys.has(id)) return@forEach
            runCatching {
                val public = publicKey(keys.obj(id))
                val signature = Base64Codec.decode(item.string("sig"))
                val verifier = Ed25519Signer().apply {
                    init(false, Ed25519PublicKeyParameters(public, 0))
                    update(payload, 0, payload.size)
                }
                if (signature.size == 64 && verifier.verifySignature(signature)) valid += id
            }
        }
        if (valid.size < descriptor.int("threshold")) fail("UPD-SIGN-003", "更新元数据没有达到角色签名阈值")
    }

    private fun publicKey(record: JsonObject): ByteArray {
        if (record.string("keytype") != "ed25519" || record.string("scheme") != "ed25519") fail("UPD-SIGN-002", "更新公钥格式无效")
        val bytes = runCatching { Base64Codec.decode(record.obj("keyval").string("public")) }
            .getOrElse { fail("UPD-SIGN-002", "更新公钥格式无效") }
        if (bytes.size != 32) fail("UPD-SIGN-002", "更新公钥长度无效")
        return bytes
    }

    private fun keyId(record: JsonObject): String = "ed25519-sha256:${JsonSupport.sha256(publicKey(record))}"
    private fun requireId(value: String, field: String): String = value.takeIf(stableId::matches)
        ?: fail("UPD-META-001", "$field 不是有效稳定 ID")
    private fun parseTime(value: String, field: String): Instant = runCatching { Instant.parse(value) }
        .getOrElse { fail("UPD-META-001", "$field 不是有效 UTC 时间") }
    private fun fail(id: String, message: String): Nothing = throw AndroidUpdateFailure(id, message)
}
