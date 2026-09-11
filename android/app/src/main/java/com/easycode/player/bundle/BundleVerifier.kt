package com.easycode.player.bundle

import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.int
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonObject
import com.google.gson.JsonArray
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import java.io.ByteArrayOutputStream
import java.io.File
import java.security.MessageDigest
import com.easycode.player.util.Base64Codec
import com.easycode.player.extension.EmbeddedExtensionRegistry
import java.util.zip.ZipEntry
import java.util.zip.ZipFile

class BundleVerificationException(val code: String, message: String, cause: Throwable? = null) :
    IllegalArgumentException("[$code] $message", cause)

data class VerifiedBundle(
    val file: File,
    val manifest: JsonObject,
    val ecir: JsonObject,
    val project: JsonObject,
    val form: JsonObject,
    val publishReport: JsonObject,
    val lock: JsonObject,
    val trustRoot: JsonObject,
    val keyId: String,
    val integritySha256: String,
    val extensionRegistry: EmbeddedExtensionRegistry = EmbeddedExtensionRegistry.empty(),
) {
    val productId: String get() = manifest.string("project_id")
    val releaseId: String get() = manifest.string("release_id")
    val title: String get() = manifest.string("name", "EasyCode Player")

    fun hasEntry(path: String): Boolean = ZipFile(file).use { it.getEntry(path) != null }

    /** Must stay byte-for-byte compatible with update_repository_v6.analyze_ecplayer_artifact. */
    fun applicationFingerprint(): String {
        val integrity = JsonSupport.parseObject(readEntry("META-INF/integrity.json"), "完整性清单")
        val applicationFiles = integrity.array("entries")
            .mapNotNull { it.takeIf(com.google.gson.JsonElement::isJsonObject)?.asJsonObject }
            .filter { record ->
                val path = record.string("path")
                path in setOf("runtime/easycode.lock", "update/config.json") || path.startsWith("runtime/extensions/")
            }
            .sortedBy { it.string("path") }
        fun sortedStrings(name: String) = publishReport.array(name).map { it.asString }.sorted()
        val permissions = JsonObject().apply {
            add("required_capabilities", JsonArray().apply { sortedStrings("required_capabilities").forEach(::add) })
            add("terminal_capabilities", JsonArray().apply { sortedStrings("player_terminal_capabilities").forEach(::add) })
            add("extension_permissions", JsonArray().apply { sortedStrings("extension_permissions").forEach(::add) })
        }
        val payload = JsonObject().apply {
            addProperty("minimum_runtime_version", manifest.string("minimum_runtime_version"))
            add("application_files", JsonArray().apply { applicationFiles.forEach { add(it.deepCopy()) } })
            addProperty("permissions_fingerprint", JsonSupport.sha256(JsonSupport.canonicalBytes(permissions)))
        }
        return JsonSupport.sha256(JsonSupport.canonicalBytes(payload))
    }

    fun readEntry(path: String, maximumBytes: Long = 64L * 1024L * 1024L): ByteArray =
        ZipFile(file).use { archive ->
            val entry = archive.getEntry(path)
                ?: throw BundleVerificationException("AND-BUNDLE-021", "Player 包缺少文件：$path")
            readBounded(archive, entry, maximumBytes)
        }
}

object BundleVerifier {
    private const val INTEGRITY_PATH = "META-INF/integrity.json"
    private const val SIGNATURE_PATH = "META-INF/signature.json"
    private const val MAX_FILES = 16_384
    private const val MAX_TOTAL_BYTES = 2L * 1024L * 1024L * 1024L
    private const val MAX_METADATA_BYTES = 16L * 1024L * 1024L
    private val requiredPaths = setOf(
        "manifest.json",
        "runtime/ecir.json",
        "runtime/project.json",
        "runtime/easycode.lock",
        "player/form.json",
        "publish-report.json",
        INTEGRITY_PATH,
        SIGNATURE_PATH,
    )
    private val forbiddenSuffixes = setOf(
        ".easy", ".py", ".pyc", ".kt", ".java", ".ts", ".tsx", ".vue", ".gradle", ".kts",
    )

    fun verify(
        bundle: File,
        trustRootBytes: ByteArray,
        extensionRegistryBytes: ByteArray = "{\"schema_version\":1,\"modules\":[]}".toByteArray(),
    ): VerifiedBundle {
        if (!bundle.isFile) fail("AND-BUNDLE-001", "Player 包不存在")
        val trustRoot = try {
            JsonSupport.parseObject(trustRootBytes, "Player 信任根")
        } catch (error: IllegalArgumentException) {
            fail("AND-BUNDLE-002", error.message ?: "Player 信任根无效", error)
        }
        if (trustRoot.int("schema_version") != 1 || trustRoot.string("algorithm") != "Ed25519") {
            fail("AND-BUNDLE-002", "Player 信任根版本或算法不受支持")
        }
        val expectedPublic = decodeBase64(trustRoot.string("public_key"), 32, "AND-BUNDLE-002", "信任根公钥")
        val expectedKeyId = "ed25519-sha256:${JsonSupport.sha256(expectedPublic)}"
        if (trustRoot.string("key_id") != expectedKeyId) {
            fail("AND-BUNDLE-002", "Player 信任根公钥指纹不一致")
        }

        ZipFile(bundle).use { archive ->
            val entries = archive.entries().toList().filterNot(ZipEntry::isDirectory)
            if (entries.size > MAX_FILES) fail("AND-BUNDLE-003", "Player 包文件数量超过安全上限")
            val names = mutableSetOf<String>()
            var total = 0L
            for (entry in entries) {
                val path = entry.name.replace('\\', '/')
                validatePath(path)
                if (path != entry.name || !names.add(path)) {
                    fail("AND-BUNDLE-004", "Player 包包含重复或非规范路径：$path")
                }
                if (entry.size < 0L || entry.size > MAX_TOTAL_BYTES - total) {
                    fail("AND-BUNDLE-005", "Player 包解压体积超过安全上限")
                }
                total += entry.size
                rejectSourcePath(path)
            }
            val missing = requiredPaths - names
            if (missing.isNotEmpty()) {
                fail("AND-BUNDLE-006", "Player 包缺少必要文件：${missing.sorted().first()}")
            }

            val integrityBytes = readBounded(archive, archive.getEntry(INTEGRITY_PATH), MAX_METADATA_BYTES)
            val signatureBytes = readBounded(archive, archive.getEntry(SIGNATURE_PATH), MAX_METADATA_BYTES)
            val integrity = parseObject(integrityBytes, "完整性清单", "AND-BUNDLE-007")
            val envelope = parseObject(signatureBytes, "签名信封", "AND-BUNDLE-007")
            if (integrity.int("schema_version") != 1 || integrity.string("hash_algorithm") != "SHA-256") {
                fail("AND-BUNDLE-008", "Player 包完整性清单版本或算法不受支持")
            }
            if (
                envelope.int("schema_version") != 1 ||
                envelope.string("algorithm") != "Ed25519" ||
                envelope.string("signed_document") != INTEGRITY_PATH
            ) {
                fail("AND-BUNDLE-009", "Player 包签名信封版本、算法或范围无效")
            }
            val publicBytes = decodeBase64(
                envelope.string("public_key"),
                32,
                "AND-BUNDLE-010",
                "发布公钥",
            )
            if (!MessageDigest.isEqual(publicBytes, expectedPublic)) {
                fail("AND-BUNDLE-011", "Player 包发布者与 APK 固定信任根不匹配")
            }
            val keyId = "ed25519-sha256:${JsonSupport.sha256(publicBytes)}"
            if (envelope.string("key_id") != keyId || keyId != expectedKeyId) {
                fail("AND-BUNDLE-012", "Player 包发布公钥指纹不一致")
            }
            val canonicalIntegrity = JsonSupport.canonicalBytes(integrity)
            val integrityDigest = JsonSupport.sha256(canonicalIntegrity)
            if (envelope.string("signed_sha256") != integrityDigest) {
                fail("AND-BUNDLE-013", "Player 包签名载荷哈希不一致")
            }
            val signature = decodeBase64(
                envelope.string("signature"),
                64,
                "AND-BUNDLE-014",
                "发布签名",
            )
            val signer = Ed25519Signer().apply {
                init(false, Ed25519PublicKeyParameters(publicBytes, 0))
                update(canonicalIntegrity, 0, canonicalIntegrity.size)
            }
            if (!signer.verifySignature(signature)) {
                fail("AND-BUNDLE-014", "Player 包发布签名验证失败")
            }

            val expectedNames = names - setOf(INTEGRITY_PATH, SIGNATURE_PATH)
            val listedNames = mutableSetOf<String>()
            val records = integrity.array("entries")
            if (records.size() == 0) fail("AND-BUNDLE-015", "完整性清单没有文件记录")
            for (raw in records) {
                if (!raw.isJsonObject) fail("AND-BUNDLE-015", "完整性记录格式无效")
                val record = raw.asJsonObject
                val path = record.string("path").replace('\\', '/')
                validatePath(path)
                if (path !in expectedNames || !listedNames.add(path)) {
                    fail("AND-BUNDLE-015", "完整性记录路径无效：$path")
                }
                val entry = archive.getEntry(path)
                    ?: fail("AND-BUNDLE-015", "完整性记录文件不存在：$path")
                val expectedSize = record.get("size")?.asLong ?: -1L
                if (expectedSize < 0L || entry.size != expectedSize) {
                    fail("AND-BUNDLE-016", "Player 包文件大小校验失败：$path")
                }
                val digest = digestEntry(archive, entry, expectedSize)
                if (record.string("sha256") != digest) {
                    fail("AND-BUNDLE-017", "Player 包文件哈希校验失败：$path")
                }
            }
            val unsigned = expectedNames - listedNames
            if (unsigned.isNotEmpty()) {
                fail("AND-BUNDLE-018", "Player 包存在未签名文件：${unsigned.sorted().first()}")
            }

            val manifest = parseEntryObject(archive, "manifest.json", "Player 清单")
            if (
                manifest.int("bundle_format") != 2 ||
                manifest.string("release_id").isBlank() ||
                manifest.string("project_id").isBlank() ||
                manifest.string("signing_key_id") != keyId ||
                manifest.bool("source_included", true)
            ) {
                fail("AND-BUNDLE-019", "Player 包版本、身份或源码隔离声明无效")
            }
            if (trustRoot.string("product_id") != manifest.string("project_id")) {
                fail("AND-BUNDLE-020", "Player 包产品身份与 APK 信任根不一致")
            }
            val lockBytes = readBounded(archive, archive.getEntry("runtime/easycode.lock"), MAX_METADATA_BYTES)
            if (manifest.string("easycode_lock_sha256") != JsonSupport.sha256(lockBytes)) {
                fail("AND-BUNDLE-022", "Player 包 easycode.lock 与清单不一致")
            }
            val lock = parseObject(lockBytes, "easycode.lock", "AND-BUNDLE-023")
            val extensions = lock.array("extensions")
            if (extensions.size() != manifest.int("extension_package_count")) {
                fail("AND-BUNDLE-024", "Player 包扩展数量与清单不一致")
            }
            val ecir = parseEntryObject(archive, "runtime/ecir.json", "ECIR")
            RuntimeRegistryContract.validate(lock, ecir)
            val project = parseEntryObject(archive, "runtime/project.json", "运行项目清单")
            val form = parseEntryObject(archive, "player/form.json", "Player 表单")
            val report = parseEntryObject(archive, "publish-report.json", "发布报告")
            if (!report.bool("valid")) fail("AND-BUNDLE-025", "Player 发布报告未通过")
            AndroidPackagePreflight.validate(ecir, project, form, report, lock)
            val extensionRegistry = EmbeddedExtensionRegistry.validate(archive, lock, extensionRegistryBytes)
            extensionRegistry.validateEcir(ecir)
            return VerifiedBundle(
                file = bundle,
                manifest = manifest,
                ecir = ecir,
                project = project,
                form = form,
                publishReport = report,
                lock = lock,
                trustRoot = trustRoot,
                keyId = keyId,
                integritySha256 = integrityDigest,
                extensionRegistry = extensionRegistry,
            )
        }
    }

    private fun parseEntryObject(archive: ZipFile, path: String, label: String): JsonObject =
        parseObject(
            readBounded(archive, archive.getEntry(path), MAX_METADATA_BYTES),
            label,
            "AND-BUNDLE-021",
        )

    private fun parseObject(bytes: ByteArray, label: String, code: String): JsonObject = try {
        JsonSupport.parseObject(bytes, label)
    } catch (error: IllegalArgumentException) {
        fail(code, error.message ?: "$label 无效", error)
    }

    private fun validatePath(path: String) {
        if (
            path.isBlank() || path.startsWith('/') || path.contains('\u0000') ||
            path.split('/').any { it.isBlank() || it == "." || it == ".." }
        ) {
            fail("AND-BUNDLE-004", "Player 包路径不安全：$path")
        }
    }

    private fun rejectSourcePath(path: String) {
        val lower = path.lowercase()
        val suffix = lower.substringAfterLast('.', "").let { if (it.isBlank()) "" else ".$it" }
        if (
            lower.startsWith("program/") || lower.startsWith(".easycode/") ||
            lower.contains("/src/") || lower.contains("/test/") || suffix in forbiddenSuffixes
        ) {
            fail("AND-BUNDLE-026", "APK 内容包意外包含源码或开发文件：$path")
        }
    }

    private fun digestEntry(archive: ZipFile, entry: ZipEntry, expectedSize: Long): String {
        val digest = MessageDigest.getInstance("SHA-256")
        var count = 0L
        archive.getInputStream(entry).use { input ->
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                count += read
                if (count > expectedSize || count > MAX_TOTAL_BYTES) {
                    fail("AND-BUNDLE-016", "Player 包文件流长度超过清单：${entry.name}")
                }
                digest.update(buffer, 0, read)
            }
        }
        if (count != expectedSize) fail("AND-BUNDLE-016", "Player 包文件流长度与清单不一致：${entry.name}")
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun decodeBase64(value: String, size: Int, code: String, label: String): ByteArray {
        val decoded = try {
            Base64Codec.decode(value)
        } catch (error: IllegalArgumentException) {
            fail(code, "$label Base64 无效", error)
        }
        if (decoded.size != size) fail(code, "$label 长度无效")
        return decoded
    }

    private fun fail(code: String, message: String, cause: Throwable? = null): Nothing =
        throw BundleVerificationException(code, message, cause)
}

internal fun readBounded(archive: ZipFile, entry: ZipEntry, maximumBytes: Long): ByteArray {
    if (entry.size < 0L || entry.size > maximumBytes) {
        throw BundleVerificationException("AND-BUNDLE-005", "Player 包文件超过读取上限：${entry.name}")
    }
    val output = ByteArrayOutputStream(entry.size.coerceAtMost(Int.MAX_VALUE.toLong()).toInt())
    var count = 0L
    archive.getInputStream(entry).use { input ->
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        while (true) {
            val read = input.read(buffer)
            if (read < 0) break
            count += read
            if (count > maximumBytes) {
                throw BundleVerificationException("AND-BUNDLE-005", "Player 包文件超过读取上限：${entry.name}")
            }
            output.write(buffer, 0, read)
        }
    }
    return output.toByteArray()
}
