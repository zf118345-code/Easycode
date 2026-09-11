package com.easycode.player.lan

import android.content.Context
import android.os.Build
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.int
import com.easycode.player.util.JsonSupport.long
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonObject
import java.io.File
import java.net.Inet4Address
import java.net.NetworkInterface
import java.security.KeyStore
import java.time.Instant
import java.util.UUID
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

internal data class LanIdentity(
    val hostId: String,
    val deviceName: String,
    val platform: String,
    val key: LanCrypto.EdIdentity,
) {
    val publicKey: ByteArray get() = key.publicKey
    val fingerprint: String get() = LanCrypto.fingerprint(publicKey)
    fun publicJson(): JsonObject = JsonObject().apply {
        addProperty("host_id", hostId)
        addProperty("device_name", deviceName)
        addProperty("platform", platform)
        addProperty("public_key", LanCrypto.b64(publicKey))
        addProperty("fingerprint", fingerprint)
    }
}

internal class AndroidLanDirectory(private val context: Context) {
    private val lock = Any()
    private val root = File(context.filesDir, "lan-v6").apply { mkdirs() }
    private val identityFile = File(root, "identity.json")
    private val stateFile = File(root, "state.json")
    val identity: LanIdentity by lazy { synchronized(lock) { loadOrCreateIdentity() } }

    fun state(): JsonObject = synchronized(lock) { readState().deepCopy() }

    fun listenerEnabled(): Boolean = synchronized(lock) { readState().bool("listener_enabled") }

    fun listenerPort(): Int = synchronized(lock) { readState().int("listener_port") }

    fun saveListener(enabled: Boolean, port: Int) = synchronized(lock) {
        val state = readState(); state.addProperty("listener_enabled", enabled); state.addProperty("listener_port", port.coerceIn(0, 65535)); writeState(state)
    }

    fun addresses(): List<String> {
        val result = linkedSetOf<String>()
        runCatching {
            NetworkInterface.getNetworkInterfaces().toList().forEach { network ->
                if (!network.isUp || network.isLoopback) return@forEach
                network.inetAddresses.toList().filterIsInstance<Inet4Address>().forEach { address ->
                    val value = address.hostAddress.orEmpty()
                    if (value.isNotBlank() && !value.startsWith("169.254.")) result += value
                }
            }
        }
        if (result.isEmpty()) result += "127.0.0.1"
        return result.sorted()
    }

    fun listPeers(): JsonArray = synchronized(lock) {
        val now = System.currentTimeMillis()
        JsonArray().apply {
            readState().array("peers").filter { it.isJsonObject && !it.asJsonObject.bool("revoked") }
                .sortedWith(compareBy({ it.asJsonObject.string("device_name").lowercase() }, { it.asJsonObject.string("host_id") }))
                .forEach { raw ->
                    val peer = raw.asJsonObject.deepCopy()
                    val seen = peer.long("last_connected_at_ms")
                    peer.addProperty("connection_state", if (seen > 0 && now - seen < 30_000) "online" else "offline")
                    add(peer)
                }
        }
    }

    fun peer(hostId: String): JsonObject = synchronized(lock) {
        readState().array("peers").firstOrNull {
            it.isJsonObject && it.asJsonObject.string("host_id") == hostId && !it.asJsonObject.bool("revoked")
        }?.asJsonObject?.deepCopy() ?: throw LanException("设备未知、未配对或已撤销", "lan.peer_unknown", action = "pair_device")
    }

    fun savePeer(
        remoteIdentity: JsonObject,
        address: String,
        port: Int,
        permissions: JsonObject,
        remotePermissions: JsonObject,
    ): JsonObject = synchronized(lock) {
        val hostId = remoteIdentity.string("host_id").trim()
        val public = LanCrypto.unb64(remoteIdentity.string("public_key"))
        if (hostId.isBlank() || hostId == identity.hostId || public.size != 32 || address.isBlank() || port !in 1..65535) {
            throw LanException("远端设备身份或地址无效", "lan.identity_invalid", action = "cancel_pairing")
        }
        val fingerprint = LanCrypto.fingerprint(public)
        val claimed = remoteIdentity.string("fingerprint")
        if (claimed.isNotBlank() && claimed != fingerprint) throw LanException("远端设备公钥指纹不一致", "lan.fingerprint_mismatch")
        val state = readState()
        val peers = state.array("peers")
        val existing = peers.firstOrNull { it.isJsonObject && it.asJsonObject.string("host_id") == hostId }?.asJsonObject
        if (existing != null && existing.string("public_key") != LanCrypto.b64(public)) {
            throw LanException("设备稳定身份的固定公钥发生变化", "lan.pinned_key_mismatch", action = "revoke_and_pair_again")
        }
        val now = System.currentTimeMillis()
        val created = existing?.long("created_at_ms")?.takeIf { it > 0 } ?: now
        val next = JsonObject().apply {
            addProperty("host_id", hostId)
            addProperty("device_name", remoteIdentity.string("device_name", hostId).take(160))
            addProperty("platform", remoteIdentity.string("platform", "unknown").take(80))
            addProperty("public_key", LanCrypto.b64(public))
            addProperty("fingerprint", fingerprint)
            add("addresses", JsonArray().apply { add(address) })
            addProperty("port", port)
            add("permissions", normalizePermissions(permissions))
            add("remote_permissions", normalizePermissions(remotePermissions))
            addProperty("created_at_ms", created)
            addProperty("updated_at_ms", now)
            addProperty("last_connected_at_ms", existing?.long("last_connected_at_ms") ?: 0L)
            addProperty("last_error_id", "")
            addProperty("revoked", false)
        }
        replaceBy(peers, "host_id", hostId, next)
        writeState(state)
        peer(hostId)
    }

    fun setPermissions(hostId: String, permissions: JsonObject): JsonObject = synchronized(lock) {
        val state = readState(); val item = findActivePeer(state, hostId)
        item.add("permissions", normalizePermissions(permissions)); item.addProperty("updated_at_ms", System.currentTimeMillis())
        writeState(state); item.deepCopy()
    }

    fun updateRemotePermissions(hostId: String, permissions: JsonObject): JsonObject = synchronized(lock) {
        val state = readState(); val item = findActivePeer(state, hostId)
        item.add("remote_permissions", normalizePermissions(permissions)); item.addProperty("updated_at_ms", System.currentTimeMillis())
        writeState(state); item.deepCopy()
    }

    fun revoke(hostId: String): JsonObject = synchronized(lock) {
        val state = readState(); val item = findActivePeer(state, hostId); val now = System.currentTimeMillis()
        item.addProperty("revoked", true); item.addProperty("revoked_at_ms", now); item.addProperty("updated_at_ms", now)
        item.add("permissions", normalizePermissions(null)); item.add("remote_permissions", normalizePermissions(null))
        removeWhere(state.array("seen_requests")) { it.string("peer_host_id") == hostId }
        removeWhere(state.array("remote_instances")) { it.string("host_id") == hostId }
        writeState(state)
        JsonObject().apply { addProperty("ok", true); addProperty("host_id", hostId); addProperty("revoked_at", Instant.ofEpochMilli(now).toString()) }
    }

    fun authorize(hostId: String, permission: String, productId: String = "", instanceId: String = ""): JsonObject {
        val peer = peer(hostId); val grants = peer.obj("permissions")
        if (!grants.bool(permission)) throw LanException("此设备未获得当前动作权限", "lan.permission_${permission}_denied", action = "review_device_permissions")
        if (permission == "remote_start") {
            val products = grants.array("allowed_products").map { it.asString }.toSet()
            val instances = grants.array("allowed_instances").map { it.asString }.toSet()
            if (products.isNotEmpty() && productId !in products) throw LanException("远程启动产品不在授权范围", "lan.remote_product_denied")
            if (instances.isNotEmpty() && instanceId !in instances) throw LanException("远程启动实例不在授权范围", "lan.remote_instance_denied")
        }
        return peer
    }

    fun markConnection(hostId: String, errorId: String = "") = synchronized(lock) {
        val state = readState(); val item = state.array("peers").firstOrNull { it.isJsonObject && it.asJsonObject.string("host_id") == hostId }?.asJsonObject ?: return@synchronized
        item.addProperty("last_connected_at_ms", if (errorId.isBlank()) System.currentTimeMillis() else item.long("last_connected_at_ms"))
        item.addProperty("last_error_id", errorId); item.addProperty("updated_at_ms", System.currentTimeMillis()); writeState(state)
    }

    fun createPairingSession(addresses: List<String>, port: Int, ttlMs: Long = 300_000): JsonObject = synchronized(lock) {
        if (ttlMs !in 1..900_000 || addresses.isEmpty() || port !in 1..65535) throw LanException("配对会话参数无效", "lan.pairing_ttl_invalid")
        val sessionId = id("pair")
        val digits = (LanCrypto.random(8).fold(0L) { acc, byte -> (acc * 257 + (byte.toInt() and 0xff)) } and 0x7fffffffL).rem(100_000_000).toString().padStart(8, '0')
        val code = digits.take(4) + "-" + digits.drop(4)
        val created = System.currentTimeMillis(); val expires = created + ttlMs
        val item = JsonObject().apply {
            addProperty("session_id", sessionId); addProperty("code_digest", JsonSupport.sha256(digits.toByteArray()))
            addProperty("pairing_key", LanCrypto.b64(LanCrypto.pairingKey(code, sessionId)))
            add("addresses", JsonSupport.fromAny(addresses)); addProperty("port", port)
            addProperty("created_at_ms", created); addProperty("expires_at_ms", expires); addProperty("used_at_ms", 0L)
            addProperty("cancelled_at_ms", 0L); addProperty("attempts", 0)
        }
        val state = readState(); state.array("pairing_sessions").add(item); writeState(state)
        val payload = JsonObject().apply {
            addProperty("version", 1); addProperty("kind", "easycode_pairing"); addProperty("session_id", sessionId); addProperty("code", code)
            add("addresses", JsonSupport.fromAny(addresses)); addProperty("port", port)
            identity.publicJson().entrySet().forEach { add(it.key, it.value.deepCopy()) }
            addProperty("expires_at", Instant.ofEpochMilli(expires).toString())
        }
        payload.deepCopy().apply {
            addProperty("qr_payload", JsonSupport.canonical(payload))
            addProperty("short_fingerprint", identity.fingerprint)
        }
    }

    fun pairingSessions(): JsonArray = synchronized(lock) {
        val state = readState(); val now = System.currentTimeMillis(); val pending = state.array("pairing_pending")
        JsonArray().apply {
            state.array("pairing_sessions").filter { it.isJsonObject && it.asJsonObject.long("expires_at_ms") > now }.forEach { raw ->
                val item = raw.asJsonObject
                add(JsonObject().apply {
                    addProperty("session_id", item.string("session_id")); addProperty("created_at", Instant.ofEpochMilli(item.long("created_at_ms")).toString())
                    addProperty("expires_at", Instant.ofEpochMilli(item.long("expires_at_ms")).toString()); addProperty("used", item.long("used_at_ms") > 0)
                    addProperty("cancelled", item.long("cancelled_at_ms") > 0); add("addresses", item.array("addresses").deepCopy()); addProperty("port", item.int("port"))
                    add("pending", JsonArray().apply { pending.filter { it.isJsonObject && it.asJsonObject.string("session_id") == item.string("session_id") }.forEach { entry ->
                        val p = entry.asJsonObject; add(JsonObject().apply { listOf("pending_id","host_id","device_name","platform","fingerprint","status").forEach { key -> addProperty(key, p.string(key)) }; addProperty("created_at", Instant.ofEpochMilli(p.long("created_at_ms")).toString()) })
                    } })
                })
            }
        }
    }

    fun acceptPairingRequest(request: JsonObject, remoteAddress: String): JsonObject = synchronized(lock) {
        val payload = request.get("payload")?.takeIf { it.isJsonObject }?.asJsonObject ?: throw LanException("配对请求格式无效", "lan.protocol_invalid")
        val state = readState(); val session = findSession(state, request.string("session_id"), request.string("code_digest"), true)
        val key = LanCrypto.unb64(session.string("pairing_key"))
        if (!LanCrypto.constantEquals(LanCrypto.hmac(key, JsonSupport.canonicalBytes(payload)), LanCrypto.unb64(request.string("mac")))) throw LanException("配对码验证失败", "lan.pairing_code_invalid")
        val remote = payload.get("identity")?.takeIf { it.isJsonObject }?.asJsonObject ?: throw LanException("发起设备身份无效", "lan.identity_invalid")
        val public = LanCrypto.unb64(remote.string("public_key")); val hostId = remote.string("host_id")
        if (public.size != 32 || hostId.isBlank() || hostId == identity.hostId || remote.string("fingerprint") != LanCrypto.fingerprint(public)) throw LanException("发起设备身份无效", "lan.identity_invalid")
        val existing = state.array("pairing_pending").firstOrNull { it.isJsonObject && it.asJsonObject.string("session_id") == session.string("session_id") && it.asJsonObject.string("host_id") == hostId }?.asJsonObject
        val pending = existing ?: JsonObject().apply {
            addProperty("pending_id", id("pending")); addProperty("session_id", session.string("session_id")); addProperty("host_id", hostId)
            addProperty("device_name", remote.string("device_name", hostId).take(160)); addProperty("platform", remote.string("platform", "unknown")); addProperty("public_key", remote.string("public_key")); addProperty("fingerprint", remote.string("fingerprint"))
            addProperty("remote_address", remoteAddress); addProperty("remote_port", payload.int("listener_port")); add("initiator_permissions", normalizePermissions(payload.obj("initiator_permissions")))
            addProperty("status", "pending"); addProperty("created_at_ms", System.currentTimeMillis()); state.array("pairing_pending").add(this)
        }
        writeState(state)
        signedPairResponse(key, JsonObject().apply {
            addProperty("status", "pending_confirmation"); addProperty("session_id", session.string("session_id")); addProperty("pending_id", pending.string("pending_id"))
            add("receiver", identity.publicJson()); addProperty("fingerprint", identity.fingerprint); addProperty("expires_at", Instant.ofEpochMilli(session.long("expires_at_ms")).toString())
        })
    }

    fun pairingStatus(request: JsonObject): JsonObject = synchronized(lock) {
        val payload = request.get("payload")?.takeIf { it.isJsonObject }?.asJsonObject ?: throw LanException("配对状态请求无效", "lan.protocol_invalid")
        val state = readState(); val session = findSession(state, request.string("session_id"), request.string("code_digest"), false); val key = LanCrypto.unb64(session.string("pairing_key"))
        if (!LanCrypto.constantEquals(LanCrypto.hmac(key, JsonSupport.canonicalBytes(payload)), LanCrypto.unb64(request.string("mac")))) throw LanException("配对码验证失败", "lan.pairing_code_invalid")
        val pending = state.array("pairing_pending").firstOrNull { it.isJsonObject && it.asJsonObject.string("pending_id") == payload.string("pending_id") && it.asJsonObject.string("session_id") == session.string("session_id") && it.asJsonObject.string("host_id") == payload.string("host_id") }?.asJsonObject ?: throw LanException("配对确认不存在", "lan.pairing_pending_unknown")
        signedPairResponse(key, JsonObject().apply {
            addProperty("status", pending.string("status")); addProperty("session_id", session.string("session_id")); addProperty("pending_id", pending.string("pending_id")); add("receiver", identity.publicJson())
            if (pending.string("status") == "confirmed") { add("receiver_permissions", pending.obj("local_permissions").deepCopy()); addProperty("address", session.array("addresses").firstOrNull()?.asString.orEmpty()); addProperty("port", session.int("port")) }
        })
    }

    fun confirmPairing(pendingId: String, permissions: JsonObject): JsonObject = synchronized(lock) {
        val state = readState(); val pending = state.array("pairing_pending").firstOrNull { it.isJsonObject && it.asJsonObject.string("pending_id") == pendingId }?.asJsonObject ?: throw LanException("配对确认已失效", "lan.pairing_session_inactive")
        val session = state.array("pairing_sessions").firstOrNull { it.isJsonObject && it.asJsonObject.string("session_id") == pending.string("session_id") }?.asJsonObject ?: throw LanException("配对确认已失效", "lan.pairing_session_inactive")
        if (pending.string("status") != "pending" || session.long("expires_at_ms") <= System.currentTimeMillis() || session.long("cancelled_at_ms") > 0) throw LanException("配对确认已失效", "lan.pairing_session_inactive")
        val remote = JsonObject().apply { listOf("host_id","device_name","platform","public_key","fingerprint").forEach { addProperty(it, pending.string(it)) } }
        val peer = savePeer(remote, pending.string("remote_address"), pending.int("remote_port"), normalizePermissions(permissions), pending.obj("initiator_permissions"))
        // savePeer commits through the same durable document. Reload before
        // updating the pending record so a stale pre-pairing snapshot cannot
        // overwrite the newly pinned peer.
        val updatedState = readState()
        val updatedPending = updatedState.array("pairing_pending").first { it.asJsonObject.string("pending_id") == pendingId }.asJsonObject
        val updatedSession = updatedState.array("pairing_sessions").first { it.asJsonObject.string("session_id") == pending.string("session_id") }.asJsonObject
        val now = System.currentTimeMillis(); updatedPending.addProperty("status", "confirmed"); updatedPending.add("local_permissions", normalizePermissions(permissions)); updatedPending.addProperty("confirmed_at_ms", now); updatedSession.addProperty("used_at_ms", now); writeState(updatedState)
        peer
    }

    fun seenResponse(peerHostId: String, requestId: String, requestHash: String): JsonObject? = synchronized(lock) {
        val state = readState(); removeWhere(state.array("seen_requests")) { it.long("expires_at_ms") <= System.currentTimeMillis() }
        val item = state.array("seen_requests").firstOrNull { it.isJsonObject && it.asJsonObject.string("peer_host_id") == peerHostId && it.asJsonObject.string("request_id") == requestId }?.asJsonObject
        writeState(state)
        if (item == null) null else {
            if (item.string("request_hash") != requestHash) throw LanException("相同请求 ID 的内容发生变化", "lan.replay_conflict")
            item.obj("response").deepCopy()
        }
    }

    fun rememberResponse(peerHostId: String, requestId: String, requestHash: String, response: JsonObject, expiresAt: Long) = synchronized(lock) {
        val state = readState(); val array = state.array("seen_requests")
        val existing = array.firstOrNull { it.isJsonObject && it.asJsonObject.string("peer_host_id") == peerHostId && it.asJsonObject.string("request_id") == requestId }?.asJsonObject
        if (existing != null) { if (existing.string("request_hash") != requestHash) throw LanException("相同请求 ID 的内容发生变化", "lan.replay_conflict"); return@synchronized }
        array.add(JsonObject().apply { addProperty("peer_host_id", peerHostId); addProperty("request_id", requestId); addProperty("request_hash", requestHash); add("response", response.deepCopy()); addProperty("expires_at_ms", expiresAt); addProperty("created_at_ms", System.currentTimeMillis()) }); writeState(state)
    }

    fun remoteInstances(): JsonArray = synchronized(lock) { readState().array("remote_instances").deepCopy() }

    fun updateRemoteCatalog(hostId: String, catalog: JsonObject) = synchronized(lock) {
        val state = readState(); val instances = state.array("remote_instances"); removeWhere(instances) { it.string("host_id") == hostId }
        catalog.array("instances").filter(JsonElement::isJsonObject).forEach { raw -> val source = raw.asJsonObject; val project = source.string("project_namespace", source.string("product_id")); val instance = source.string("instance_id"); if (project.isNotBlank() && instance.isNotBlank()) instances.add(source.deepCopy().apply { addProperty("host_id", hostId); addProperty("project_namespace", project); addProperty("observed_at_ms", System.currentTimeMillis()) }) }
        writeState(state)
    }

    fun diagnostic(eventType: String, level: String = "info", peerHostId: String = "", requestId: String = "", correlationId: String = "", errorId: String = "", details: JsonObject = JsonObject()) = synchronized(lock) {
        val state = readState(); val values = state.array("diagnostics")
        val safe = JsonObject(); details.entrySet().filter { it.key !in setOf("code","pairing_key","private_key","session_key","body","content") && it.value.isJsonPrimitive }.forEach { safe.add(it.key, it.value.deepCopy()) }
        values.add(JsonObject().apply { addProperty("sequence", values.size() + 1); addProperty("recorded_at", Instant.now().toString()); addProperty("level", level); addProperty("event_type", eventType); addProperty("peer_host_id", peerHostId); addProperty("request_id", requestId); addProperty("correlation_id", correlationId); addProperty("error_id", errorId); add("details", safe) })
        while (values.size() > 2_000) values.remove(0); writeState(state)
    }

    fun diagnostics(): JsonArray = synchronized(lock) { readState().array("diagnostics").deepCopy() }

    private fun findSession(state: JsonObject, sessionId: String, digest: String, increment: Boolean): JsonObject {
        val item = state.array("pairing_sessions").firstOrNull { it.isJsonObject && ((sessionId.isNotBlank() && it.asJsonObject.string("session_id") == sessionId) || (sessionId.isBlank() && it.asJsonObject.string("code_digest") == digest)) }?.asJsonObject
        if (item == null || item.long("cancelled_at_ms") > 0 || item.long("expires_at_ms") <= System.currentTimeMillis() || item.int("attempts") >= 12) throw LanException("配对码错误、过期或尝试次数过多", "lan.pairing_code_invalid")
        if (increment) { item.addProperty("attempts", item.int("attempts") + 1); writeState(state) }
        return item
    }

    private fun signedPairResponse(key: ByteArray, value: JsonObject): JsonObject = value.apply { addProperty("proof", LanCrypto.b64(LanCrypto.hmac(key, JsonSupport.canonicalBytes(this)))) }

    private fun findActivePeer(state: JsonObject, hostId: String): JsonObject = state.array("peers").firstOrNull { it.isJsonObject && it.asJsonObject.string("host_id") == hostId && !it.asJsonObject.bool("revoked") }?.asJsonObject ?: throw LanException("设备未知或已撤销", "lan.peer_unknown")

    private fun normalizePermissions(raw: JsonObject?): JsonObject = JsonObject().apply {
        listOf("messages", "status", "remote_start").forEach { addProperty(it, raw?.bool(it) == true) }
        listOf("allowed_products", "allowed_instances").forEach { name -> add(name, JsonArray().apply { raw?.array(name)?.mapNotNull { runCatching { it.asString.trim() }.getOrNull() }?.filter(String::isNotBlank)?.distinct()?.sorted()?.forEach(::add) }) }
        if (!bool("remote_start")) { add("allowed_products", JsonArray()); add("allowed_instances", JsonArray()) }
    }

    private fun readState(): JsonObject {
        if (!stateFile.isFile) return newState()
        return runCatching { JsonSupport.parseObject(stateFile.readBytes(), "LAN 状态") }.getOrElse { throw LanException("LAN 本地状态损坏", "lan.database_unavailable", cause = it) }.also { if (it.int("schema_version") != 1) throw LanException("LAN 数据版本不受支持", "lan.database_version") }
    }

    private fun writeState(state: JsonObject) = AtomicFiles.write(stateFile, JsonSupport.canonicalBytes(state))

    private fun newState() = JsonObject().apply { addProperty("schema_version", 1); addProperty("listener_enabled", false); addProperty("listener_port", 0); listOf("peers","pairing_sessions","pairing_pending","seen_requests","remote_instances","diagnostics").forEach { add(it, JsonArray()) } }

    private fun loadOrCreateIdentity(): LanIdentity {
        if (Build.VERSION.SDK_INT < 23) {
            throw LanException(
                "安全消息与局域网协作需要 Android 6.0 或以上",
                "lan.platform_unsupported",
            )
        }
        if (identityFile.isFile) {
            try {
                val raw = JsonSupport.parseObject(identityFile.readBytes(), "设备身份")
                val seed = decryptSeed(LanCrypto.unb64(raw.string("encrypted_seed")), LanCrypto.unb64(raw.string("iv")))
                val key = LanCrypto.EdIdentity(seed); val public = key.publicKey
                if (LanCrypto.b64(public) != raw.string("public_key") || !raw.string("host_id").startsWith("host_")) throw IllegalArgumentException("identity")
                return LanIdentity(raw.string("host_id"), raw.string("device_name"), raw.string("platform"), key)
            } catch (error: Exception) { throw LanException("设备身份记录已损坏", "lan.identity_corrupt", action = "export_diagnostics", cause = error) }
        }
        val key = LanCrypto.generateIdentity(); val (iv, encrypted) = encryptSeed(key.seed)
        val value = JsonObject().apply { addProperty("schema_version", 1); addProperty("host_id", id("host")); addProperty("device_name", Build.MANUFACTURER + " " + Build.MODEL); addProperty("platform", "android"); addProperty("algorithm", "ed25519"); addProperty("public_key", LanCrypto.b64(key.publicKey)); addProperty("fingerprint", LanCrypto.fingerprint(key.publicKey)); addProperty("protection", "android-keystore-aes-gcm-v1"); addProperty("iv", LanCrypto.b64(iv)); addProperty("encrypted_seed", LanCrypto.b64(encrypted)); addProperty("created_at", Instant.now().toString()) }
        AtomicFiles.write(identityFile, JsonSupport.canonicalBytes(value)); return LanIdentity(value.string("host_id"), value.string("device_name"), value.string("platform"), key)
    }

    @android.annotation.TargetApi(23)
    private fun secretKey(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(KeyGenParameterSpec.Builder(KEY_ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).setRandomizedEncryptionRequired(true).build())
        return generator.generateKey()
    }

    @android.annotation.TargetApi(23)
    private fun encryptSeed(seed: ByteArray): Pair<ByteArray, ByteArray> { val cipher = Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE, secretKey()); return cipher.iv to cipher.doFinal(seed) }
    @android.annotation.TargetApi(23)
    private fun decryptSeed(value: ByteArray, iv: ByteArray): ByteArray { val cipher = Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.DECRYPT_MODE, secretKey(), GCMParameterSpec(128, iv)); return cipher.doFinal(value) }

    private fun replaceBy(array: JsonArray, key: String, value: String, next: JsonObject) { for (index in 0 until array.size()) if (array[index].isJsonObject && array[index].asJsonObject.string(key) == value) { array.set(index, next); return }; array.add(next) }
    private fun removeWhere(array: JsonArray, predicate: (JsonObject) -> Boolean) { for (index in array.size() - 1 downTo 0) if (array[index].isJsonObject && predicate(array[index].asJsonObject)) array.remove(index) }
    private fun id(prefix: String) = "${prefix}_${UUID.randomUUID().toString().replace("-", "")}" 

    companion object {
        private const val KEY_ALIAS = "easycode.lan.identity.seed.v1"
    }
}
