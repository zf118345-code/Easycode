package com.easycode.player.extension

import com.easycode.extension.api.AndroidExtensionContext
import com.easycode.extension.api.AndroidExtensionFunction
import com.easycode.player.bundle.BundleVerificationException
import com.easycode.player.util.Base64Codec
import com.easycode.player.util.JsonSupport
import com.google.gson.JsonObject
import java.io.ByteArrayOutputStream
import java.nio.file.Files
import java.security.SecureRandom
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue
import org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import org.junit.Test

class EmbeddedExtensionRegistryTest {
    @Test
    fun signedStaticModuleAndEcirContractAreAccepted() {
        val fixture = fixture()
        ZipFile(fixture.archive).use { archive ->
            val registry = EmbeddedExtensionRegistry.validate(archive, fixture.lock, fixture.registry)
            assertEquals(HarnessExtension::class.java.name, registry.entries.getValue(FUNCTION_ID).className)
            assertEquals("int64", registry.entries.getValue(FUNCTION_ID).returnType)
            registry.validateEcir(ecir("int64"))
        }
    }

    @Test
    fun publisherSignatureIsRecheckedOnDevice() {
        val fixture = fixture(corruptSignature = true)
        ZipFile(fixture.archive).use { archive ->
            val error = assertFailsWith<BundleVerificationException> {
                EmbeddedExtensionRegistry.validate(archive, fixture.lock, fixture.registry)
            }
            assertEquals("AND-EXT-006", error.code)
            assertTrue(error.message.orEmpty().contains("签名"))
        }
    }

    @Test
    fun ecirCannotChangeSignedReturnTypeOrCallAnUnlinkedFunction() {
        val fixture = fixture()
        ZipFile(fixture.archive).use { archive ->
            val registry = EmbeddedExtensionRegistry.validate(archive, fixture.lock, fixture.registry)
            assertEquals(
                "AND-EXT-008",
                assertFailsWith<BundleVerificationException> { registry.validateEcir(ecir("string")) }.code,
            )
            assertEquals(
                "AND-EXT-008",
                assertFailsWith<BundleVerificationException> {
                    registry.validateEcir(ecir("int64", "extension.harness.missing"))
                }.code,
            )
        }
    }

    @Test
    fun apkRegistryCannotEscalateExtensionPermissions() {
        val fixture = fixture()
        val tamperedRegistry = fixture.registry.toString(Charsets.UTF_8)
            .replaceFirst("\"permissions\":[]", "\"permissions\":[\"network\"]")
            .toByteArray()
        ZipFile(fixture.archive).use { archive ->
            val error = assertFailsWith<BundleVerificationException> {
                EmbeddedExtensionRegistry.validate(archive, fixture.lock, tamperedRegistry)
            }
            assertEquals("AND-EXT-005", error.code)
            assertTrue(error.message.orEmpty().contains("权限闭包"))
        }
    }

    private data class Fixture(
        val archive: java.io.File,
        val lock: JsonObject,
        val registry: ByteArray,
    )

    private fun fixture(corruptSignature: Boolean = false): Fixture {
        val module = "static-harness-module".toByteArray()
        val moduleSha = JsonSupport.sha256(module)
        val runtime = value(
            mapOf(
                "format" to "ecx-runtime-1",
                "package_id" to PACKAGE_ID,
                "version" to VERSION,
                "variant_id" to VARIANT_ID,
                "host" to "android_native",
                "runtime" to "android-kotlin-v1",
                "minimum_android_api" to 24,
                "targets" to listOf("android_native"),
                "module" to MODULE_PATH,
                "entrypoints" to mapOf(FUNCTION_ID to HarnessExtension::class.java.name),
                "files" to listOf(mapOf("path" to MODULE_PATH, "size" to module.size, "sha256" to moduleSha)),
            ),
        )
        val artifact = zip(mapOf("ecx-runtime.json" to JsonSupport.canonicalBytes(runtime), MODULE_PATH to module))
        val artifactSha = JsonSupport.sha256(artifact)
        val privateKey = Ed25519PrivateKeyParameters(SecureRandom())
        val publicKey = privateKey.generatePublicKey().encoded
        val keyId = "ed25519-sha256:${JsonSupport.sha256(publicKey)}"
        val signer = Ed25519Signer().apply {
            init(true, privateKey)
            update(artifact, 0, artifact.size)
        }
        val signatureValue = value(
            mapOf(
                "signature_version" to 1,
                "algorithm" to "Ed25519",
                "package_id" to PACKAGE_ID,
                "version" to VERSION,
                "variant_id" to VARIANT_ID,
                "key_id" to keyId,
                "public_key" to Base64Codec.encode(publicKey),
                "signed_sha256" to artifactSha,
                "signature" to Base64Codec.encode(signer.generateSignature().also {
                    if (corruptSignature) it[0] = (it[0].toInt() xor 1).toByte()
                }),
            ),
        )
        val signatureBytes = JsonSupport.canonicalBytes(signatureValue)
        val signatureSha = JsonSupport.sha256(signatureBytes)
        val contract = value(
            mapOf(
                "function_id" to FUNCTION_ID,
                "contract_version" to "1.0.0",
                "return_type" to "int64",
            ),
        )
        val contractFingerprint = JsonSupport.sha256(JsonSupport.canonicalBytes(contract))
        val variant = mapOf(
            "target" to "android_native",
            "host" to "android_native",
            "runtime" to "android-kotlin-v1",
            "minimum_android_api" to 24,
            "variant_id" to VARIANT_ID,
            "artifact_path" to ARTIFACT_PATH,
            "artifact_signature_path" to SIGNATURE_PATH,
            "artifact_sha256" to artifactSha,
            "artifact_signature_sha256" to signatureSha,
            "entrypoints" to mapOf(FUNCTION_ID to HarnessExtension::class.java.name),
        )
        val descriptor = value(
            mapOf(
                "runtime_extension_schema" to 1,
                "package_id" to PACKAGE_ID,
                "version" to VERSION,
                "publisher_id" to PUBLISHER_ID,
                "publisher_key_fingerprint" to keyId,
                "publisher_public_key" to Base64Codec.encode(publicKey),
                "manifest_sha256" to "1".repeat(64),
                "content_sha256" to "2".repeat(64),
                "trust_mode" to "local_trusted_code",
                "permissions" to emptyList<String>(),
                "network" to mapOf("allow" to emptyList<String>()),
                "dependencies" to emptyList<Any>(),
                "contributions" to emptyList<Any>(),
                "function_contracts" to listOf(JsonSupport.toAny(contract)),
                "variants" to listOf(variant),
            ),
        )
        val selected = variant.filterKeys { it !in setOf("artifact_path", "artifact_signature_path", "entrypoints") }
        val lock = value(
            mapOf(
                "extensions" to listOf(
                    mapOf(
                        "package_id" to PACKAGE_ID,
                        "version" to VERSION,
                        "scope" to "project",
                        "manifest_sha256" to "1".repeat(64),
                        "content_sha256" to "2".repeat(64),
                        "publisher_id" to PUBLISHER_ID,
                        "publisher_key_fingerprint" to keyId,
                        "publisher_public_key" to Base64Codec.encode(publicKey),
                        "trust_mode" to "local_trusted_code",
                        "dependencies" to emptyList<Any>(),
                        "contributions" to emptyList<Any>(),
                        "selected_variants" to listOf(selected),
                        "function_contracts" to listOf(
                            mapOf(
                                "function_id" to FUNCTION_ID,
                                "contract_version" to "1.0.0",
                                "contract_fingerprint" to contractFingerprint,
                            ),
                        ),
                    ),
                ),
            ),
        )
        val registry = JsonSupport.canonicalBytes(
            value(
                mapOf(
                    "schema_version" to 1,
                    "modules" to listOf(
                        mapOf(
                            "package_id" to PACKAGE_ID,
                            "variant_id" to VARIANT_ID,
                            "minimum_android_api" to 24,
                            "artifact_sha256" to artifactSha,
                            "module_sha256" to moduleSha,
                            "permissions" to emptyList<String>(),
                            "declared_permissions" to emptyList<String>(),
                            "android_manifest_permissions" to emptyList<String>(),
                            "entrypoints" to listOf(
                                mapOf("function_id" to FUNCTION_ID, "class_name" to HarnessExtension::class.java.name),
                            ),
                        ),
                    ),
                ),
            ),
        )
        val archiveFile = Files.createTempFile("easycode-extension-registry", ".zip").toFile()
        archiveFile.writeBytes(
            zip(
                mapOf(
                    "runtime/extensions/$PACKAGE_ID/extension.json" to JsonSupport.canonicalBytes(descriptor),
                    ARTIFACT_PATH to artifact,
                    SIGNATURE_PATH to signatureBytes,
                ),
            ),
        )
        return Fixture(archiveFile, lock, registry)
    }

    private fun ecir(returnType: String, functionId: String = FUNCTION_ID) = value(
        mapOf(
            "functions" to listOf(
                mapOf(
                    "function_id" to "function.main",
                    "instructions" to listOf(
                        mapOf(
                            "instruction_id" to "statement.extension",
                            "opcode" to "call.extension",
                            "callee_function_id" to functionId,
                            "timeout_ms" to 1_000,
                            "result_type" to returnType,
                            "arguments" to emptyMap<String, Any?>(),
                        ),
                    ),
                ),
            ),
        ),
    )

    private fun value(value: Any?): JsonObject = JsonSupport.fromAny(value).asJsonObject

    private fun zip(entries: Map<String, ByteArray>): ByteArray = ByteArrayOutputStream().use { output ->
        ZipOutputStream(output).use { archive ->
            entries.forEach { (path, bytes) ->
                archive.putNextEntry(ZipEntry(path))
                archive.write(bytes)
                archive.closeEntry()
            }
        }
        output.toByteArray()
    }

    class HarnessExtension : AndroidExtensionFunction {
        override fun invoke(context: AndroidExtensionContext, requestJson: String): String = "7"
    }

    companion object {
        private const val PACKAGE_ID = "com.easycode.harness"
        private const val PUBLISHER_ID = "com.easycode.tests"
        private const val VERSION = "1.0.0"
        private const val VARIANT_ID = "android.api24"
        private const val FUNCTION_ID = "extension.harness.add"
        private const val MODULE_PATH = "runtime/harness.jar"
        private const val ARTIFACT_PATH = "runtime/extensions/$PACKAGE_ID/$VARIANT_ID.ecxrt"
        private const val SIGNATURE_PATH = "$ARTIFACT_PATH.sig"
    }
}
