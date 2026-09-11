package com.easycode.player.extension

import com.easycode.extension.api.AndroidExtensionFunction
import com.easycode.player.bundle.BundleVerificationException
import com.easycode.player.util.Base64Codec
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.int
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonObject
import com.google.gson.JsonElement
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import java.io.ByteArrayInputStream
import java.security.MessageDigest
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream

data class EmbeddedExtensionEntrypoint(
    val packageId: String,
    val variantId: String,
    val functionId: String,
    val className: String,
    val minimumAndroidApi: Int,
    val artifactSha256: String,
    val moduleSha256: String,
    val returnType: String,
)

class EmbeddedExtensionRegistry private constructor(
    val entries: Map<String, EmbeddedExtensionEntrypoint>,
) {
    fun validateEcir(ecir: JsonObject) {
        walk(ecir) { instruction ->
            if (instruction.string("opcode") != "call.extension") return@walk
            val instructionId = instruction.string("instruction_id")
            val functionId = instruction.string("callee_function_id")
            val entry = entries[functionId]
                ?: fail("AND-EXT-008", "ECIR 引用了未静态链接的 Android 扩展函数：$instructionId/$functionId")
            val timeout = instruction.get("timeout_ms")?.takeUnless(JsonElement::isJsonNull)?.asLong ?: 30_000L
            if (timeout !in 50L..600_000L) {
                fail("AND-EXT-008", "Android 扩展调用超时契约无效：$instructionId")
            }
            if (instruction.string("result_type", "any") != entry.returnType) {
                fail("AND-EXT-008", "Android 扩展调用返回类型与签名契约不一致：$instructionId")
            }
        }
    }

    companion object {
        private const val MAX_ARTIFACT_BYTES = 512L * 1024L * 1024L
        private const val MAX_MODULE_BYTES = 256L * 1024L * 1024L

        fun empty(): EmbeddedExtensionRegistry = EmbeddedExtensionRegistry(emptyMap())

        fun validate(
            archive: ZipFile,
            lock: JsonObject,
            registryBytes: ByteArray,
        ): EmbeddedExtensionRegistry {
            val registry = try {
                JsonSupport.parseObject(registryBytes, "APK 扩展注册表")
            } catch (error: IllegalArgumentException) {
                fail("AND-EXT-002", error.message ?: "APK 扩展注册表无效", error)
            }
            if (registry.int("schema_version") != 1) {
                fail("AND-EXT-002", "APK 扩展注册表版本不受支持")
            }
            val embedded = linkedMapOf<Pair<String, String>, JsonObject>()
            for (raw in registry.array("modules")) {
                if (!raw.isJsonObject) fail("AND-EXT-002", "APK 扩展模块记录格式无效")
                val module = raw.asJsonObject
                val key = module.string("package_id") to module.string("variant_id")
                if (key.first.isBlank() || key.second.isBlank() || embedded.put(key, module) != null) {
                    fail("AND-EXT-002", "APK 扩展模块身份缺失或重复")
                }
            }

            val entries = linkedMapOf<String, EmbeddedExtensionEntrypoint>()
            val expectedModules = linkedSetOf<Pair<String, String>>()
            for (rawExtension in lock.array("extensions")) {
                if (!rawExtension.isJsonObject) fail("AND-EXT-003", "扩展锁记录格式无效")
                val locked = rawExtension.asJsonObject
                val packageId = locked.string("package_id")
                val descriptorPath = "runtime/extensions/$packageId/extension.json"
                val descriptor = parseOuterObject(archive, descriptorPath, "扩展发布描述")
                validateDescriptorIdentity(descriptor, locked, packageId)
                val contractReturnTypes = validateFunctionContracts(descriptor, locked, packageId)
                val variants = descriptor.array("variants").mapNotNull {
                    it.takeIf { value -> value.isJsonObject }?.asJsonObject
                }
                val selectedVariants = locked.array("selected_variants")
                val publishedKeys = variants.map { it.string("target") to it.string("variant_id") }
                val lockedKeys = selectedVariants.map { raw ->
                    if (!raw.isJsonObject) fail("AND-EXT-003", "扩展锁定变体格式无效")
                    raw.asJsonObject.string("target") to raw.asJsonObject.string("variant_id")
                }
                if (
                    publishedKeys.size != publishedKeys.toSet().size ||
                    lockedKeys.size != lockedKeys.toSet().size ||
                    publishedKeys.toSet() != lockedKeys.toSet()
                ) {
                    fail("AND-EXT-003", "扩展发布变体闭包与签名锁不一致：$packageId")
                }
                for (rawVariant in selectedVariants) {
                    if (!rawVariant.isJsonObject) fail("AND-EXT-003", "扩展锁定变体格式无效")
                    val selected = rawVariant.asJsonObject
                    if (
                        selected.string("host") != "android_native" ||
                        selected.string("runtime") != "android-kotlin-v1"
                    ) {
                        fail("AND-EXT-004", "APK 包含非 Android Kotlin/JVM 扩展变体：$packageId")
                    }
                    val variantId = selected.string("variant_id")
                    val variant = variants.firstOrNull {
                        it.string("variant_id") == variantId &&
                            it.string("target") == selected.string("target")
                    } ?: fail("AND-EXT-003", "扩展发布描述缺少锁定变体：$packageId/$variantId")
                    val key = packageId to variantId
                    if (!expectedModules.add(key)) continue
                    val moduleRecord = embedded[key]
                        ?: fail("AND-EXT-005", "APK 没有静态链接扩展模块：$packageId/$variantId")
                    val minimumApi = selected.int("minimum_android_api")
                    val artifactSha = selected.string("artifact_sha256")
                    val artifactSignatureSha = selected.string("artifact_signature_sha256")
                    if (
                        minimumApi !in 21..37 ||
                        moduleRecord.int("minimum_android_api") != minimumApi ||
                        moduleRecord.string("artifact_sha256") != artifactSha ||
                        variant.int("minimum_android_api") != minimumApi ||
                        variant.string("artifact_sha256") != artifactSha ||
                        artifactSignatureSha.isBlank() ||
                        variant.string("artifact_signature_sha256") != artifactSignatureSha
                    ) {
                        fail("AND-EXT-005", "APK 扩展注册表与签名锁不一致：$packageId/$variantId")
                    }
                    val artifactPath = variant.string("artifact_path")
                    val artifactBytes = readOuterBounded(archive, artifactPath, MAX_ARTIFACT_BYTES)
                    if (sha256(artifactBytes) != artifactSha) {
                        fail("AND-EXT-006", "扩展密封产物哈希不一致：$packageId/$variantId")
                    }
                    verifyPublisherSignature(archive, descriptor, variant, artifactBytes, packageId, variantId)
                    val sealed = readSealed(
                        artifactBytes,
                        packageId,
                        descriptor.string("version"),
                        variantId,
                    )
                    if (
                        sealed.descriptor.string("host") != "android_native" ||
                        sealed.descriptor.string("runtime") != "android-kotlin-v1" ||
                        sealed.descriptor.int("minimum_android_api") != minimumApi ||
                        sealed.descriptor.string("module") != sealed.modulePath ||
                        sealed.moduleSha256 != moduleRecord.string("module_sha256")
                    ) {
                        fail("AND-EXT-006", "扩展 JAR 与密封描述或 APK 注册表不一致：$packageId/$variantId")
                    }
                    val declared = variant.getAsJsonObject("entrypoints")?.entrySet()
                        ?.associate { it.key to it.value.asString }
                        ?: emptyMap()
                    val sealedEntries = sealed.descriptor.getAsJsonObject("entrypoints")?.entrySet()
                        ?.associate { it.key to it.value.asString }
                        ?: emptyMap()
                    val registered = moduleRecord.array("entrypoints").associate { raw ->
                        if (!raw.isJsonObject) fail("AND-EXT-005", "APK 扩展入口记录格式无效")
                        raw.asJsonObject.string("function_id") to raw.asJsonObject.string("class_name")
                    }
                    if (declared != sealedEntries || declared != registered) {
                        fail("AND-EXT-005", "APK 扩展函数入口与签名描述不一致：$packageId/$variantId")
                    }
                    val declaredPermissions = stringArray(descriptor, "permissions", packageId)
                    val functionPermissions = descriptor.array("function_contracts")
                        .mapNotNull { raw -> raw.takeIf(JsonElement::isJsonObject)?.asJsonObject }
                        .filter { it.string("function_id") in registered }
                        .flatMap { stringArray(it, "permissions", packageId) }
                        .distinct()
                        .sorted()
                    val registeredPermissions = stringArray(moduleRecord, "permissions", packageId)
                    val registeredDeclaredPermissions = stringArray(
                        moduleRecord, "declared_permissions", packageId,
                    )
                    val registeredManifestPermissions = stringArray(
                        moduleRecord, "android_manifest_permissions", packageId,
                    )
                    if (
                        declaredPermissions != registeredDeclaredPermissions ||
                        functionPermissions != registeredPermissions ||
                        androidManifestPermissions(declaredPermissions) != registeredManifestPermissions ||
                        functionPermissions.any { it !in declaredPermissions } ||
                        minimumApi < (functionPermissions.maxOfOrNull {
                            PERMISSION_MINIMUM_API[it]
                                ?: fail("AND-EXT-005", "Android 扩展声明未知权限：$packageId/$it")
                        } ?: 21)
                    ) {
                        fail("AND-EXT-005", "APK 扩展权限闭包与签名契约不一致：$packageId/$variantId")
                    }
                    for ((functionId, className) in registered) {
                        if (functionId.isBlank() || className.isBlank() || functionId in entries) {
                            fail("AND-EXT-005", "APK 扩展函数入口缺失或重复：$functionId")
                        }
                        val implementation = try {
                            Class.forName(className)
                        } catch (error: ClassNotFoundException) {
                            fail("AND-EXT-007", "APK 未链接扩展入口类：$functionId -> $className", error)
                        }
                        if (!AndroidExtensionFunction::class.java.isAssignableFrom(implementation)) {
                            fail("AND-EXT-007", "扩展入口没有实现 EasyCode Android ABI：$functionId -> $className")
                        }
                        entries[functionId] = EmbeddedExtensionEntrypoint(
                            packageId, variantId, functionId, className, minimumApi,
                            artifactSha, sealed.moduleSha256,
                            contractReturnTypes[functionId]
                                ?: fail("AND-EXT-005", "扩展入口缺少函数契约：$functionId"),
                        )
                    }
                }
            }
            if (embedded.keys != expectedModules) {
                fail("AND-EXT-005", "APK 扩展注册表包含未锁定模块")
            }
            return EmbeddedExtensionRegistry(entries)
        }

        private fun validateDescriptorIdentity(descriptor: JsonObject, locked: JsonObject, packageId: String) {
            val scalarFields = listOf(
                "package_id", "version", "publisher_id", "publisher_key_fingerprint",
                "publisher_public_key", "manifest_sha256", "content_sha256", "trust_mode",
            )
            val structuredFields = listOf("dependencies", "contributions")
            if (
                descriptor.int("runtime_extension_schema") != 1 ||
                scalarFields.any { descriptor.get(it) != locked.get(it) } ||
                structuredFields.any { descriptor.get(it) != locked.get(it) }
            ) {
                fail("AND-EXT-003", "扩展发布描述与签名锁不一致：$packageId")
            }
        }

        private val PERMISSION_MINIMUM_API = mapOf(
            "filesystem.read" to 21,
            "filesystem.write" to 21,
            "host.launch_application" to 21,
            "messaging" to 23,
            "network" to 21,
            "target.control.read" to 21,
            "target.frame.read" to 21,
            "target.input" to 24,
        )

        private val PERMISSION_MANIFEST = mapOf(
            "filesystem.read" to emptyList(),
            "filesystem.write" to emptyList(),
            "host.launch_application" to emptyList(),
            "messaging" to listOf(
                "android.permission.INTERNET",
                "android.permission.ACCESS_NETWORK_STATE",
                "android.permission.ACCESS_WIFI_STATE",
                "android.permission.CHANGE_WIFI_MULTICAST_STATE",
            ),
            "network" to listOf(
                "android.permission.INTERNET",
                "android.permission.ACCESS_NETWORK_STATE",
            ),
            "target.control.read" to emptyList(),
            "target.frame.read" to listOf(
                "android.permission.FOREGROUND_SERVICE",
                "android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION",
            ),
            "target.input" to emptyList(),
        )

        private fun stringArray(value: JsonObject, name: String, packageId: String): List<String> {
            val result = value.array(name).map { raw ->
                if (!raw.isJsonPrimitive || !raw.asJsonPrimitive.isString) {
                    fail("AND-EXT-005", "Android 扩展权限列表无效：$packageId/$name")
                }
                raw.asString
            }
            if (result.size != result.distinct().size) {
                fail("AND-EXT-005", "Android 扩展权限列表不能重复：$packageId/$name")
            }
            return result.sorted()
        }

        private fun androidManifestPermissions(permissionIds: List<String>): List<String> =
            permissionIds.flatMap { permission ->
                PERMISSION_MANIFEST[permission]
                    ?: fail("AND-EXT-005", "Android 扩展声明未知权限：$permission")
            }.distinct().sorted()

        private fun validateFunctionContracts(
            descriptor: JsonObject,
            locked: JsonObject,
            packageId: String,
        ): Map<String, String> {
            val lockedContracts = linkedMapOf<String, JsonObject>()
            for (raw in locked.array("function_contracts")) {
                if (!raw.isJsonObject) fail("AND-EXT-003", "扩展函数锁记录格式无效：$packageId")
                val contract = raw.asJsonObject
                val functionId = contract.string("function_id")
                if (functionId.isBlank() || lockedContracts.put(functionId, contract) != null) {
                    fail("AND-EXT-003", "扩展函数锁身份缺失或重复：$packageId/$functionId")
                }
            }
            val returnTypes = linkedMapOf<String, String>()
            for (raw in descriptor.array("function_contracts")) {
                if (!raw.isJsonObject) fail("AND-EXT-003", "扩展函数契约格式无效：$packageId")
                val contract = raw.asJsonObject
                val functionId = contract.string("function_id")
                val expected = lockedContracts[functionId]
                    ?: fail("AND-EXT-003", "扩展函数契约未被锁定：$packageId/$functionId")
                if (
                    contract.string("contract_version") != expected.string("contract_version") ||
                    sha256(JsonSupport.canonicalBytes(contract)) != expected.string("contract_fingerprint") ||
                    returnTypes.put(functionId, contract.string("return_type")) != null
                ) {
                    fail("AND-EXT-003", "扩展函数契约与签名锁不一致：$packageId/$functionId")
                }
            }
            if (returnTypes.keys != lockedContracts.keys || returnTypes.values.any(String::isBlank)) {
                fail("AND-EXT-003", "扩展函数契约闭包不完整：$packageId")
            }
            return returnTypes
        }

        private fun verifyPublisherSignature(
            archive: ZipFile,
            descriptor: JsonObject,
            variant: JsonObject,
            artifactBytes: ByteArray,
            packageId: String,
            variantId: String,
        ) {
            val signaturePath = variant.string("artifact_signature_path")
            val signatureBytes = readOuterBounded(archive, signaturePath, 16L * 1024L * 1024L)
            if (sha256(signatureBytes) != variant.string("artifact_signature_sha256")) {
                fail("AND-EXT-006", "扩展发布签名哈希不一致：$packageId/$variantId")
            }
            val envelope = try {
                JsonSupport.parseObject(signatureBytes, "扩展发布签名")
            } catch (error: IllegalArgumentException) {
                fail("AND-EXT-006", error.message ?: "扩展发布签名无效", error)
            }
            val publicKey = try {
                Base64Codec.decode(envelope.string("public_key"))
            } catch (error: IllegalArgumentException) {
                fail("AND-EXT-006", "扩展发布公钥无效：$packageId/$variantId", error)
            }
            val expectedKeyId = "ed25519-sha256:${sha256(publicKey)}"
            if (
                envelope.int("signature_version") != 1 ||
                envelope.string("algorithm") != "Ed25519" ||
                envelope.string("package_id") != packageId ||
                envelope.string("version") != descriptor.string("version") ||
                envelope.string("variant_id") != variantId ||
                publicKey.size != 32 ||
                envelope.string("key_id") != expectedKeyId ||
                descriptor.string("publisher_key_fingerprint") != expectedKeyId ||
                descriptor.string("publisher_public_key") != envelope.string("public_key") ||
                envelope.string("signed_sha256") != sha256(artifactBytes)
            ) {
                fail("AND-EXT-006", "扩展发布签名身份不一致：$packageId/$variantId")
            }
            val signature = try {
                Base64Codec.decode(envelope.string("signature"))
            } catch (error: IllegalArgumentException) {
                fail("AND-EXT-006", "扩展发布签名编码无效：$packageId/$variantId", error)
            }
            val verifier = Ed25519Signer().apply {
                init(false, Ed25519PublicKeyParameters(publicKey, 0))
                update(artifactBytes, 0, artifactBytes.size)
            }
            if (signature.size != 64 || !verifier.verifySignature(signature)) {
                fail("AND-EXT-006", "扩展发布签名验证失败：$packageId/$variantId")
            }
        }

        private data class SealedModule(
            val descriptor: JsonObject,
            val modulePath: String,
            val moduleSha256: String,
        )

        private fun walk(value: JsonElement, visitor: (JsonObject) -> Unit) {
            when {
                value.isJsonArray -> value.asJsonArray.forEach { walk(it, visitor) }
                value.isJsonObject -> {
                    val objectValue = value.asJsonObject
                    if (objectValue.get("instruction_id")?.isJsonPrimitive == true) visitor(objectValue)
                    objectValue.entrySet().forEach { walk(it.value, visitor) }
                }
            }
        }

        private fun readSealed(
            bytes: ByteArray,
            packageId: String,
            version: String,
            variantId: String,
        ): SealedModule {
            var descriptorBytes: ByteArray? = null
            val files = linkedMapOf<String, ByteArray>()
            var fileCount = 0
            var totalBytes = 0L
            ZipInputStream(ByteArrayInputStream(bytes)).use { input ->
                while (true) {
                    val entry = input.nextEntry ?: break
                    if (entry.isDirectory) continue
                    fileCount += 1
                    if (fileCount > 4_096) fail("AND-EXT-006", "扩展密封文件数量超过安全上限")
                    val name = entry.name.replace('\\', '/')
                    if (name.isBlank() || name.startsWith('/') || name.split('/').any { it.isBlank() || it == "." || it == ".." }) {
                        fail("AND-EXT-006", "扩展密封路径不安全：$name")
                    }
                    val payload = input.readBounded(if (name == "ecx-runtime.json") 16L * 1024L * 1024L else MAX_MODULE_BYTES)
                    totalBytes += payload.size
                    if (totalBytes > MAX_ARTIFACT_BYTES) fail("AND-EXT-006", "扩展密封解压体积超过安全上限")
                    if (name == "ecx-runtime.json") {
                        if (descriptorBytes != null) fail("AND-EXT-006", "扩展密封描述路径重复")
                        descriptorBytes = payload
                    } else if (files.put(name, payload) != null) {
                        fail("AND-EXT-006", "扩展密封路径重复：$name")
                    }
                }
            }
            val descriptor = try {
                JsonSupport.parseObject(descriptorBytes ?: fail("AND-EXT-006", "扩展密封描述缺失"), "扩展密封描述")
            } catch (error: IllegalArgumentException) {
                fail("AND-EXT-006", error.message ?: "扩展密封描述无效", error)
            }
            if (
                descriptor.string("format") != "ecx-runtime-1" ||
                descriptor.string("package_id") != packageId ||
                descriptor.string("version") != version ||
                descriptor.string("variant_id") != variantId
            ) {
                fail("AND-EXT-006", "扩展密封描述身份无效：$packageId/$variantId")
            }
            val modulePath = descriptor.string("module")
            val module = files[modulePath] ?: fail("AND-EXT-006", "扩展密封 JAR module 缺失：$modulePath")
            val listed = descriptor.array("files").associate { raw ->
                if (!raw.isJsonObject) fail("AND-EXT-006", "扩展密封文件记录无效")
                raw.asJsonObject.string("path") to raw.asJsonObject
            }
            if (listed.keys != files.keys) fail("AND-EXT-006", "扩展密封文件闭包不一致")
            for ((path, payload) in files) {
                val record = listed.getValue(path)
                if (record.get("size")?.asLong != payload.size.toLong() || record.string("sha256") != sha256(payload)) {
                    fail("AND-EXT-006", "扩展密封文件校验失败：$path")
                }
            }
            return SealedModule(descriptor, modulePath, sha256(module))
        }

        private fun parseOuterObject(archive: ZipFile, path: String, label: String): JsonObject = try {
            JsonSupport.parseObject(readOuterBounded(archive, path, 16L * 1024L * 1024L), label)
        } catch (error: IllegalArgumentException) {
            fail("AND-EXT-003", error.message ?: "$label 无效", error)
        }

        private fun readOuterBounded(archive: ZipFile, path: String, maximum: Long): ByteArray {
            val entry = archive.getEntry(path) ?: fail("AND-EXT-003", "扩展文件缺失：$path")
            if (entry.size < 0 || entry.size > maximum) fail("AND-EXT-003", "扩展文件超过安全上限：$path")
            return archive.getInputStream(entry).use { it.readBounded(maximum) }
        }

        private fun java.io.InputStream.readBounded(maximum: Long): ByteArray {
            val output = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
            var total = 0L
            while (true) {
                val count = read(buffer)
                if (count < 0) break
                total += count
                if (total > maximum) fail("AND-EXT-003", "扩展文件流超过安全上限")
                output.write(buffer, 0, count)
            }
            return output.toByteArray()
        }

        private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
            .digest(bytes).joinToString("") { "%02x".format(it) }

        private fun fail(code: String, message: String, cause: Throwable? = null): Nothing =
            throw BundleVerificationException(code, message, cause)
    }
}
