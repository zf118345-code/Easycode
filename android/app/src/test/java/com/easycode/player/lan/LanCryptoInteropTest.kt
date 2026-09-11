package com.easycode.player.lan

import com.easycode.player.util.JsonSupport
import com.google.gson.JsonParser
import org.bouncycastle.crypto.params.X25519PrivateKeyParameters
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LanCryptoInteropTest {
    @Test fun pythonPairingVectorMatches() {
        assertEquals("HUHgIx_4dWJ7IsAm-Ddqi7BZBdgsjug61L9J5HqARqI", LanCrypto.b64(LanCrypto.pairingKey("1234-5678", "pair_abc")))
    }

    @Test fun pythonEd25519VectorMatches() {
        val identity = LanCrypto.EdIdentity(ByteArray(32) { it.toByte() }); val message = "easycode-test".toByteArray()
        assertEquals("A6EHv_POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg", LanCrypto.b64(identity.publicKey))
        assertEquals("KdZ6UaY7ECQKBmy061gAB1wIc095hxAEfKvJrC6tIunSvvzNHe-QPeBYB3GmaQiG6srU7OKC_D1NoSNWMGX1Ag", LanCrypto.b64(identity.sign(message)))
        assertTrue(LanCrypto.verify(identity.publicKey, message, identity.sign(message)))
        assertFalse(LanCrypto.verify(identity.publicKey, "changed".toByteArray(), identity.sign(message)))
    }

    @Test fun pythonX25519VectorMatches() {
        val first = LanCrypto.XKey(X25519PrivateKeyParameters(ByteArray(32) { (it + 1).toByte() }, 0)); val second = LanCrypto.XKey(X25519PrivateKeyParameters(ByteArray(32) { (it + 33).toByte() }, 0))
        assertEquals("B6N8vBQgk8i3VdwbEOhstCY3StFqqFPtC9_AsrhtHHw", LanCrypto.b64(first.publicKey))
        assertEquals("WGmv9FBUlzLLqu1eXfmzCm2jHLDldCutWtShp2jxpns", LanCrypto.b64(second.publicKey))
        assertEquals("qE3Hw8jwWLGy3EzR6bXcCnmH-ItqlWTN4zkfxCEVnnc", LanCrypto.b64(first.exchange(second.publicKey)))
        assertArrayEquals(first.exchange(second.publicKey), second.exchange(first.publicKey))
    }

    @Test fun canonicalJsonIsDeterministicAndUtf8() {
        val value = JsonParser.parseString("{\"z\":2,\"a\":[1,true,null],\"中文\":\"值\"}")
        assertEquals("{\"a\":[1,true,null],\"z\":2,\"中文\":\"值\"}", JsonSupport.canonical(value))
    }

    @Test fun authenticatedEncryptionRejectsTampering() {
        val key = ByteArray(32) { it.toByte() }; val nonce = ByteArray(12) { (it + 3).toByte() }; val aad = "aad".toByteArray(); val plain = "跨平台消息".toByteArray()
        val encrypted = LanCrypto.encrypt(key, nonce, aad, plain)
        assertArrayEquals(plain, LanCrypto.decrypt(key, nonce, aad, encrypted)); encrypted[0] = (encrypted[0].toInt() xor 1).toByte()
        val error = runCatching { LanCrypto.decrypt(key, nonce, aad, encrypted) }.exceptionOrNull() as LanException
        assertEquals("lan.authentication_failed", error.errorId)
    }
}
