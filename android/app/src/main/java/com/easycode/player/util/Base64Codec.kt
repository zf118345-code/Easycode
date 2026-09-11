package com.easycode.player.util

import org.bouncycastle.util.encoders.Base64

/** API-21-safe Base64 shared by Android runtime and plain JVM contract tests. */
internal object Base64Codec {
    fun encode(value: ByteArray, urlSafe: Boolean = false, padded: Boolean = true): String {
        var encoded = Base64.toBase64String(value)
        if (urlSafe) encoded = encoded.replace('+', '-').replace('/', '_')
        return if (padded) encoded else encoded.trimEnd('=')
    }

    fun decode(value: String, urlSafe: Boolean = false): ByteArray {
        var normalized = value.filterNot(Char::isWhitespace)
        if (urlSafe) normalized = normalized.replace('-', '+').replace('_', '/')
        require(normalized.length % 4 != 1) { "Base64 长度无效" }
        normalized += "=".repeat((4 - normalized.length % 4) % 4)
        return Base64.decode(normalized)
    }
}
