package com.easycode.player.lan

import com.easycode.player.util.JsonSupport
import com.google.gson.JsonElement
import org.bouncycastle.crypto.digests.SHA256Digest
import org.bouncycastle.crypto.generators.HKDFBytesGenerator
import org.bouncycastle.crypto.generators.PKCS5S2ParametersGenerator
import org.bouncycastle.crypto.macs.HMac
import org.bouncycastle.crypto.modes.ChaCha20Poly1305
import org.bouncycastle.crypto.params.AEADParameters
import org.bouncycastle.crypto.params.HKDFParameters
import org.bouncycastle.crypto.params.KeyParameter
import org.bouncycastle.crypto.params.X25519PrivateKeyParameters
import org.bouncycastle.crypto.params.X25519PublicKeyParameters
import org.bouncycastle.crypto.params.Ed25519PrivateKeyParameters
import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import java.security.MessageDigest
import java.security.SecureRandom
import com.easycode.player.util.Base64Codec

internal object LanCrypto {
    private val random = SecureRandom()

    fun random(size: Int): ByteArray = ByteArray(size).also(random::nextBytes)

    fun b64(value: ByteArray): String = Base64Codec.encode(value, urlSafe = true, padded = false)

    fun unb64(value: String): ByteArray = try {
        Base64Codec.decode(value, urlSafe = true)
    } catch (error: IllegalArgumentException) {
        throw LanException("安全传输字段编码无效", "lan.protocol_invalid", cause = error)
    }

    fun sha256(value: ByteArray): ByteArray = MessageDigest.getInstance("SHA-256").digest(value)

    fun sha256Text(value: ByteArray): String = "sha256:" + sha256(value).joinToString("") { "%02x".format(it) }

    fun canonical(value: JsonElement): ByteArray = JsonSupport.canonicalBytes(value)

    fun fingerprint(publicKey: ByteArray): String {
        val value = sha256(publicKey).joinToString("") { "%02X".format(it) }
        return (0 until 32 step 4).joinToString("-") { value.substring(it, it + 4) }
    }

    fun pairingKey(code: String, sessionId: String): ByteArray {
        val normalized = code.uppercase().filter(Char::isLetterOrDigit)
        if (normalized.length < 8) throw LanException("配对码格式无效", "lan.pairing_code_invalid")
        val generator = PKCS5S2ParametersGenerator(SHA256Digest())
        generator.init(normalized.toByteArray(Charsets.US_ASCII), sessionId.toByteArray(), 120_000)
        return (generator.generateDerivedParameters(256) as KeyParameter).key
    }

    fun hmac(key: ByteArray, value: ByteArray): ByteArray {
        val mac = HMac(SHA256Digest())
        mac.init(KeyParameter(key))
        mac.update(value, 0, value.size)
        return ByteArray(mac.macSize).also { mac.doFinal(it, 0) }
    }

    fun constantEquals(left: ByteArray, right: ByteArray): Boolean = MessageDigest.isEqual(left, right)

    data class EdIdentity(val seed: ByteArray) {
        private val privateKey = Ed25519PrivateKeyParameters(seed, 0)
        val publicKey: ByteArray get() = privateKey.generatePublicKey().encoded

        fun sign(value: ByteArray): ByteArray {
            val signer = Ed25519Signer()
            signer.init(true, privateKey)
            signer.update(value, 0, value.size)
            return signer.generateSignature()
        }
    }

    fun generateIdentity(): EdIdentity = EdIdentity(random(32))

    fun verify(publicKey: ByteArray, value: ByteArray, signature: ByteArray): Boolean = try {
        val signer = Ed25519Signer()
        signer.init(false, Ed25519PublicKeyParameters(publicKey, 0))
        signer.update(value, 0, value.size)
        signer.verifySignature(signature)
    } catch (_: Exception) {
        false
    }

    data class XKey(val privateKey: X25519PrivateKeyParameters) {
        val publicKey: ByteArray get() = privateKey.generatePublicKey().encoded
        fun exchange(remote: ByteArray): ByteArray = ByteArray(32).also {
            privateKey.generateSecret(X25519PublicKeyParameters(remote, 0), it, 0)
        }
    }

    fun generateX25519(): XKey = XKey(X25519PrivateKeyParameters(random))

    fun hkdf(shared: ByteArray, salt: ByteArray, info: ByteArray, size: Int = 64): ByteArray {
        val generator = HKDFBytesGenerator(SHA256Digest())
        generator.init(HKDFParameters(shared, salt, info))
        return ByteArray(size).also { generator.generateBytes(it, 0, size) }
    }

    fun encrypt(key: ByteArray, nonce: ByteArray, aad: ByteArray, plain: ByteArray): ByteArray = aead(true, key, nonce, aad, plain)

    fun decrypt(key: ByteArray, nonce: ByteArray, aad: ByteArray, cipher: ByteArray): ByteArray = try {
        aead(false, key, nonce, aad, cipher)
    } catch (error: Exception) {
        throw LanException("安全帧认证失败", "lan.authentication_failed", cause = error)
    }

    private fun aead(encrypting: Boolean, key: ByteArray, nonce: ByteArray, aad: ByteArray, input: ByteArray): ByteArray {
        val cipher = ChaCha20Poly1305()
        cipher.init(encrypting, AEADParameters(KeyParameter(key), 128, nonce, aad))
        val output = ByteArray(cipher.getOutputSize(input.size))
        val written = cipher.processBytes(input, 0, input.size, output, 0)
        val final = cipher.doFinal(output, written)
        return output.copyOf(written + final)
    }
}

internal class LanException(
    message: String,
    val errorId: String = "lan.transport_unavailable",
    val transient: Boolean = false,
    val action: String = "retry",
    cause: Throwable? = null,
) : RuntimeException(message, cause)
