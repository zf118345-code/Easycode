package com.easycode.player.bundle

import com.easycode.player.util.JsonSupport.int
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonObject

/** Frozen cross-language identity of executable pure value semantics. */
internal object RuntimeRegistryContract {
    const val VERSION = 10
    const val CONTENT_HASH = "76b831b768e17a40f3093ac42ead01104e5761803da924670865ed75f01203d3"

    fun validate(lock: JsonObject, ecir: JsonObject) {
        val toolchain = lock.obj("toolchain")
        if (
            toolchain.int("pure_value_registry_version", -1) != VERSION ||
            toolchain.string("pure_value_registry_sha256") != CONTENT_HASH
        ) {
            throw BundleVerificationException(
                "AND-BUNDLE-027",
                "easycode.lock 纯值注册表与 Android Runtime v$VERSION 不兼容",
            )
        }
        val ecirRegistry = ecir.obj("pure_operation_registry")
        if (
            ecirRegistry.int("registry_version", -1) != VERSION ||
            ecirRegistry.string("content_hash") != CONTENT_HASH
        ) {
            throw BundleVerificationException(
                "AND-BUNDLE-027",
                "ECIR 纯值注册表与 Android Runtime v$VERSION 不兼容",
            )
        }
        if (
            ecirRegistry.int("registry_version") != toolchain.int("pure_value_registry_version") ||
            ecirRegistry.string("content_hash") != toolchain.string("pure_value_registry_sha256")
        ) {
            throw BundleVerificationException("AND-BUNDLE-027", "ECIR 与 easycode.lock 纯值注册表身份不一致")
        }
    }
}
