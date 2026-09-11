package com.easycode.player.update

import com.easycode.player.util.JsonSupport
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.util.Base64

class AndroidUpdateProtocolTest {
    private val privateKey = Ed25519PrivateKeyParameters(ByteArray(32) { (it + 1).toByte() }, 0)
    private val publicKey = privateKey.generatePublicKey().encoded
    private val keyId = "ed25519-sha256:${JsonSupport.sha256(publicKey)}"

    @Test
    fun rootRequiresAValidThresholdSignatureAndRejectsTampering() {
        val envelope = signedEnvelope(root())
        assertEquals(1, AndroidUpdateProtocol.initialRoot(envelope, "player.test").get("version").asInt)
        envelope.getAsJsonObject("signed").addProperty("version", 2)
        assertEquals("UPD-SIGN-003", assertThrows(AndroidUpdateFailure::class.java) {
            AndroidUpdateProtocol.initialRoot(envelope, "player.test")
        }.errorId)
    }

    @Test
    fun initialRootRejectsExpiredPinnedMetadata() {
        val envelope = signedEnvelope(root())
        assertEquals("UPD-EXPIRED-001", assertThrows(AndroidUpdateFailure::class.java) {
            AndroidUpdateProtocol.initialRoot(envelope, "player.test", Instant.parse("2036-01-01T00:00:00Z"))
        }.errorId)
    }

    @Test
    fun roleIdentityCompatibilityAndMetadataHashAreVerified() {
        val root = AndroidUpdateProtocol.initialRoot(signedEnvelope(root()), "player.test")
        val signed = JsonObject().apply {
            addProperty("_type", "targets")
            addProperty("spec_version", 1)
            addProperty("product_id", "player.test")
            addProperty("domain", "project_content")
            addProperty("version", 1)
            addProperty("issued_at", "2026-01-01T00:00:00Z")
            addProperty("expires", "2035-01-01T00:00:00Z")
            add("releases", JsonArray())
        }
        val bytes = JsonSupport.canonicalBytes(signedEnvelope(signed))
        val verified = AndroidUpdateProtocol.role(
            JsonSupport.parseObject(bytes, "targets"), root, "targets", "player.test",
            "project_content", 1, Instant.parse("2027-01-01T00:00:00Z"),
        )
        assertEquals("targets", verified.get("_type").asString)
        val record = JsonObject().apply {
            addProperty("length", bytes.size)
            add("hashes", JsonObject().apply { addProperty("sha256", JsonSupport.sha256(bytes)) })
        }
        AndroidUpdateProtocol.verifyMetadata(bytes, record, "targets.json")
        assertEquals("UPD-MIXMATCH-001", assertThrows(AndroidUpdateFailure::class.java) {
            AndroidUpdateProtocol.verifyMetadata(bytes + byteArrayOf(0), record, "targets.json")
        }.errorId)
        assertTrue(AndroidUpdateProtocol.versionInRange("6.0.0-debug", "5.0.0", "7.0.0"))
        assertTrue(!AndroidUpdateProtocol.versionInRange("8.0.0", "5.0.0", "7.0.0"))
    }

    @Test
    fun androidArtifactSelectionDoesNotIgnoreRuntimeContracts() {
        val release = JsonObject().apply {
            add("artifacts", JsonArray().apply { add(artifact()) })
        }
        assertNotNull(AndroidUpdateProtocol.compatibleArtifact(release, "project_content", "x86_64", "6.0.0", "6.0.0"))
        assertEquals(null, AndroidUpdateProtocol.compatibleArtifact(release, "project_content", "x86_64", "9.0.0", "6.0.0"))
    }

    private fun root() = JsonObject().apply {
        addProperty("_type", "root")
        addProperty("spec_version", 1)
        addProperty("product_id", "player.test")
        addProperty("version", 1)
        addProperty("expires", "2035-01-01T00:00:00Z")
        addProperty("consistent_snapshot", true)
        add("mirrors", JsonArray().apply { add("https://updates.example.test/player") })
        add("keys", JsonObject().apply {
            add(keyId, JsonObject().apply {
                addProperty("keytype", "ed25519")
                addProperty("scheme", "ed25519")
                add("keyval", JsonObject().apply { addProperty("public", Base64.getEncoder().encodeToString(publicKey)) })
            })
        })
        add("roles", JsonObject().apply {
            listOf("root", "timestamp", "snapshot", "targets", "rollout", "policy").forEach { role ->
                add(role, JsonObject().apply {
                    add("keyids", JsonArray().apply { add(keyId) })
                    addProperty("threshold", 1)
                })
            }
        })
    }

    private fun artifact() = JsonObject().apply {
        addProperty("artifact_id", "content-x86")
        addProperty("kind", "project_content")
        addProperty("platform", "android")
        addProperty("architecture", "x86_64")
        addProperty("path", "artifacts/content.ecplayer")
        addProperty("length", 10)
        add("hashes", JsonObject().apply { addProperty("sha256", "a".repeat(64)) })
        addProperty("runtime_min", "5.0.0")
        addProperty("runtime_max", "7.0.0")
        addProperty("ecir_min", "5.0.0")
        addProperty("ecir_max", "7.0.0")
        addProperty("application_fingerprint", "b".repeat(64))
        addProperty("content_fingerprint", "c".repeat(64))
        addProperty("permissions_fingerprint", "d".repeat(64))
        add("abi", JsonArray())
        addProperty("install_boundary", "atomic_content_slot")
    }

    private fun signedEnvelope(signed: JsonObject): JsonObject {
        val bytes = JsonSupport.canonicalBytes(signed)
        val signer = Ed25519Signer().apply { init(true, privateKey); update(bytes, 0, bytes.size) }
        return JsonObject().apply {
            add("signed", signed.deepCopy())
            add("signatures", JsonArray().apply {
                add(JsonObject().apply {
                    addProperty("keyid", keyId)
                    addProperty("sig", Base64.getEncoder().encodeToString(signer.generateSignature()))
                })
            })
        }
    }
}
