package com.easycode.player.bundle

import com.easycode.player.util.JsonSupport
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import org.junit.Test

class RuntimeRegistryContractTest {
    @Test
    fun exactV5LockAndEcirRegistryAreAccepted() {
        RuntimeRegistryContract.validate(lock(), ecir())
    }

    @Test
    fun staleLockVersionOrHashIsRejectedBeforeRuntime() {
        val staleVersion = lock().apply {
            getAsJsonObject("toolchain").addProperty("pure_value_registry_version", 4)
        }
        val staleHash = lock().apply {
            getAsJsonObject("toolchain").addProperty("pure_value_registry_sha256", "0".repeat(64))
        }

        assertEquals(
            "AND-BUNDLE-027",
            assertFailsWith<BundleVerificationException> {
                RuntimeRegistryContract.validate(staleVersion, ecir())
            }.code,
        )
        assertEquals(
            "AND-BUNDLE-027",
            assertFailsWith<BundleVerificationException> {
                RuntimeRegistryContract.validate(staleHash, ecir())
            }.code,
        )
    }

    @Test
    fun staleOrMissingEcirRegistryIsRejectedBeforeRuntime() {
        val stale = ecir().apply {
            getAsJsonObject("pure_operation_registry").addProperty("registry_version", 4)
        }

        assertEquals(
            "AND-BUNDLE-027",
            assertFailsWith<BundleVerificationException> {
                RuntimeRegistryContract.validate(lock(), stale)
            }.code,
        )
        assertEquals(
            "AND-BUNDLE-027",
            assertFailsWith<BundleVerificationException> {
                RuntimeRegistryContract.validate(lock(), JsonSupport.fromAny(emptyMap<String, Any?>()).asJsonObject)
            }.code,
        )
    }

    private fun lock() = JsonSupport.fromAny(
        mapOf(
            "toolchain" to mapOf(
                "pure_value_registry_version" to RuntimeRegistryContract.VERSION,
                "pure_value_registry_sha256" to RuntimeRegistryContract.CONTENT_HASH,
            ),
        ),
    ).asJsonObject

    private fun ecir() = JsonSupport.fromAny(
        mapOf(
            "pure_operation_registry" to mapOf(
                "registry_version" to RuntimeRegistryContract.VERSION,
                "content_hash" to RuntimeRegistryContract.CONTENT_HASH,
            ),
        ),
    ).asJsonObject
}
