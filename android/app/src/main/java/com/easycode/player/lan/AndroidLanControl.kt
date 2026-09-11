package com.easycode.player.lan

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
import java.io.DataInputStream
import java.io.DataOutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.time.Instant
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledExecutorService
import java.util.concurrent.TimeUnit

internal class AndroidLanControl(private val directory: AndroidLanDirectory) {
    private val executor = Executors.newCachedThreadPool { task -> Thread(task, "easycode-android-lan").apply { isDaemon = false } }
    private var maintenance: ScheduledExecutorService? = null
    private val handlers = ConcurrentHashMap<String, (JsonObject, JsonObject) -> JsonObject>()
    private val tickHandlers = CopyOnWriteArrayList<() -> Unit>()
    @Volatile private var statusProvider: () -> JsonObject = { JsonObject().apply { add("instances", JsonArray()) } }
    @Volatile private var server: ServerSocket? = null
    @Volatile private var udp: DatagramSocket? = null
    @Volatile private var port = 0

    val identity: LanIdentity get() = directory.identity
    val running: Boolean get() = server?.isClosed == false
    val configuredEnabled: Boolean get() = directory.listenerEnabled()

    fun setStatusProvider(value: () -> JsonObject) { statusProvider = value }
    fun registerHandler(type: String, handler: (JsonObject, JsonObject) -> JsonObject) { handlers[type] = handler }
    fun registerTickHandler(handler: () -> Unit) { if (!tickHandlers.contains(handler)) tickHandlers += handler }

    @Synchronized fun start(): JsonObject {
        if (running) return status()
        val preferred = directory.listenerPort()
        val socket = ServerSocket().apply { reuseAddress = true; bind(InetSocketAddress("0.0.0.0", preferred)); soTimeout = 500 }
        val discovery = DatagramSocket(null).apply { reuseAddress = true; broadcast = true; bind(InetSocketAddress("0.0.0.0", socket.localPort)); soTimeout = 500 }
        server = socket; udp = discovery; port = socket.localPort; directory.saveListener(true, port)
        executor.execute(::acceptLoop); executor.execute(::discoveryLoop)
        maintenance = Executors.newSingleThreadScheduledExecutor { task -> Thread(task, "easycode-lan-maintenance").apply { isDaemon = false } }.also { scheduler ->
            scheduler.scheduleWithFixedDelay({ tickHandlers.forEach { runCatching(it) } }, 250, 500, TimeUnit.MILLISECONDS)
        }
        directory.diagnostic("listener.started", details = JsonObject().apply { addProperty("port", port) })
        return status()
    }

    @Synchronized fun stop(): JsonObject {
        server?.close(); udp?.close(); server = null; udp = null; maintenance?.shutdownNow(); maintenance = null
        directory.saveListener(false, port); directory.diagnostic("listener.stopped")
        return JsonObject().apply { addProperty("ok", true); addProperty("state", "stopped") }
    }

    fun restoreIfEnabled() { if (directory.listenerEnabled()) runCatching { start() }.onFailure { directory.diagnostic("listener.restore_failed", "warning", errorId = (it as? LanException)?.errorId ?: "lan.listener_bind_failed") } }

    fun status(): JsonObject = JsonObject().apply {
        addProperty("available", true); addProperty("running", running); add("identity", identity.publicJson())
        add("addresses", JsonSupport.fromAny(if (running) directory.addresses() else emptyList<String>())); addProperty("port", port)
        add("permissions", JsonSupport.fromAny(listOf("messages", "remote_start", "status"))); add("paired_devices", directory.listPeers()); add("remote_instances", directory.remoteInstances()); add("pairing_sessions", directory.pairingSessions())
        add("cloud_relay", JsonObject().apply { addProperty("available", false); addProperty("state", "not_in_product_scope") })
    }

    fun createPairingSession(ttlMs: Long = 300_000): JsonObject { if (!running) start(); return directory.createPairingSession(directory.addresses(), port, ttlMs) }
    fun confirmPairing(pendingId: String, permissions: JsonObject) = directory.confirmPairing(pendingId, permissions)
    fun setPermissions(hostId: String, permissions: JsonObject) = directory.setPermissions(hostId, permissions)
    fun revoke(hostId: String) = directory.revoke(hostId)
    fun diagnostics(): JsonArray = directory.diagnostics()

    fun discover(timeoutMs: Int = 700, targetPort: Int = port): JsonArray {
        if (targetPort !in 1..65535) throw LanException("发现需要监听端口", "lan.discovery_port_unknown")
        val result = linkedMapOf<String, JsonObject>()
        DatagramSocket().use { socket ->
            socket.broadcast = true; socket.soTimeout = 100
            val request = JsonObject().apply { addProperty("magic", DISCOVERY_MAGIC); addProperty("version", 1); addProperty("nonce", LanCrypto.b64(LanCrypto.random(12))) }
            val bytes = JsonSupport.canonicalBytes(request)
            directory.addresses().forEach { address ->
                runCatching {
                    val parts = address.split('.').map(String::toInt)
                    val broadcast = if (parts.size == 4) "${parts[0]}.${parts[1]}.${parts[2]}.255" else "255.255.255.255"
                    socket.send(DatagramPacket(bytes, bytes.size, InetAddress.getByName(broadcast), targetPort))
                }
            }
            runCatching { socket.send(DatagramPacket(bytes, bytes.size, InetAddress.getByName("255.255.255.255"), targetPort)) }
            val deadline = System.currentTimeMillis() + timeoutMs.coerceIn(50, 5_000)
            while (System.currentTimeMillis() < deadline) {
                try {
                    val buffer = ByteArray(8192); val packet = DatagramPacket(buffer, buffer.size); socket.receive(packet)
                    val value = JsonSupport.parseObject(buffer.copyOf(packet.length), "发现应答")
                    if (value.string("magic") == DISCOVERY_MAGIC && value.string("host_id") != identity.hostId) { value.addProperty("address", packet.address.hostAddress.orEmpty()); result[value.string("host_id")] = value }
                } catch (_: SocketTimeoutException) { }
            }
        }
        return JsonArray().apply { result.values.forEach(::add) }
    }

    fun beginPairing(address: String, targetPort: Int, code: String, sessionId: String, permissions: JsonObject): JsonObject {
        if (!running) start()
        val payload = JsonObject().apply { add("identity", identity.publicJson()); addProperty("listener_port", port); add("initiator_permissions", permissions.deepCopy()); addProperty("nonce", LanCrypto.b64(LanCrypto.random(16))); addProperty("timestamp_ms", System.currentTimeMillis()) }
        val response = plainRequest(address, targetPort, pairingRequest("pair.request", sessionId, code, payload))
        verifyPairResponse(response, sessionId, code)
        return response.apply { addProperty("address", address); addProperty("port", targetPort); addProperty("code", code); add("initiator_permissions", permissions.deepCopy()) }
    }

    fun completePairing(pairing: JsonObject, expectedFingerprint: String = ""): JsonObject {
        val payload = JsonObject().apply { addProperty("pending_id", pairing.string("pending_id")); addProperty("host_id", identity.hostId); addProperty("nonce", LanCrypto.b64(LanCrypto.random(16))); addProperty("timestamp_ms", System.currentTimeMillis()) }
        val response = plainRequest(pairing.string("address"), pairing.int("port"), pairingRequest("pair.status", pairing.string("session_id"), pairing.string("code"), payload))
        verifyPairResponse(response, pairing.string("session_id"), pairing.string("code"))
        if (response.string("status") != "confirmed") return response
        val receiver = response.obj("receiver"); val actual = receiver.string("fingerprint")
        if (expectedFingerprint.isNotBlank() && expectedFingerprint != actual) throw LanException("用户确认的设备指纹与连接设备不一致", "lan.fingerprint_mismatch")
        return directory.savePeer(receiver, pairing.string("address"), pairing.int("port"), pairing.obj("initiator_permissions"), response.obj("receiver_permissions"))
    }

    fun refresh(hostId: String): JsonObject {
        secureRequest(hostId, "permissions.query", JsonObject(), ttlMs = 15_000)
        return secureRequest(hostId, "status.query", JsonObject(), ttlMs = 15_000).also { directory.updateRemoteCatalog(hostId, it) }
    }

    fun secureRequest(hostId: String, requestType: String, payload: JsonObject, requestId: String = id("request"), ttlMs: Long = 30_000): JsonObject {
        val peer = directory.peer(hostId); val permission = permissionFor(requestType); val remote = peer.obj("remote_permissions")
        if (permission != null && !remote.bool(permission)) throw LanException("远端设备没有授予当前动作权限", "lan.remote_permission_${permission}_denied")
        val now = System.currentTimeMillis(); val request = JsonObject().apply { addProperty("request_id", requestId); addProperty("request_type", requestType); addProperty("timestamp_ms", now); addProperty("expires_at_ms", now + ttlMs.coerceIn(1, MAX_TTL_MS)); add("payload", payload.deepCopy()) }
        var last: Exception? = null
        for (rawAddress in peer.array("addresses")) {
            try {
                Socket().use { socket ->
                    socket.connect(InetSocketAddress(rawAddress.asString, peer.int("port")), 5_000); socket.soTimeout = 10_000
                    val keys = clientHandshake(socket, peer); sendFrame(socket, encryptFrame(keys.sendKey, keys.sessionId, request)); val frame = receiveFrame(socket)
                    if (frame.string("type") != "secure.frame") throw errorFrom(frame)
                    val response = decryptFrame(keys.receiveKey, keys.sessionId, frame)
                    if (!response.bool("ok")) throw errorFrom(response)
                    directory.markConnection(hostId)
                    val result = response.obj("result").deepCopy()
                    if (requestType == "permissions.query") directory.updateRemotePermissions(hostId, result.obj("permissions"))
                    return result
                }
            } catch (error: Exception) { last = error; if (error is LanException && !error.transient && error.errorId !in setOf("lan.device_unreachable","lan.connection_interrupted")) throw error }
        }
        directory.markConnection(hostId, (last as? LanException)?.errorId ?: "lan.device_unreachable")
        throw (last as? LanException ?: LanException("配对设备当前不可达", "lan.device_unreachable", true, cause = last))
    }

    private fun acceptLoop() {
        while (running) try { val client = server?.accept() ?: break; client.soTimeout = 10_000; executor.execute { serve(client) } } catch (_: SocketTimeoutException) { } catch (_: Exception) { if (running) directory.diagnostic("listener.accept_failed", "warning", errorId = "lan.connection_interrupted") }
    }

    private fun discoveryLoop() {
        while (running) try {
            val socket = udp ?: break; val buffer = ByteArray(8192); val packet = DatagramPacket(buffer, buffer.size); socket.receive(packet)
            val request = JsonSupport.parseObject(buffer.copyOf(packet.length), "发现请求")
            if (request.string("magic") != DISCOVERY_MAGIC || request.int("version") != 1) continue
            val response = JsonObject().apply { addProperty("magic", DISCOVERY_MAGIC); addProperty("version", 1); identity.publicJson().entrySet().forEach { add(it.key, it.value.deepCopy()) }; addProperty("address", packet.address.hostAddress.orEmpty()); addProperty("port", port); addProperty("pairable", directory.pairingSessions().size() > 0) }
            val bytes = JsonSupport.canonicalBytes(response); socket.send(DatagramPacket(bytes, bytes.size, packet.address, packet.port))
        } catch (_: SocketTimeoutException) { } catch (_: Exception) { if (running) directory.diagnostic("discovery.failed", "warning", errorId = "lan.protocol_invalid") }
    }

    private fun serve(socket: Socket) = socket.use { connection ->
        try {
            val first = receiveFrame(connection)
            when (first.string("type")) {
                "pair.request" -> sendFrame(connection, ok(directory.acceptPairingRequest(first, connection.inetAddress.hostAddress.orEmpty())))
                "pair.status" -> sendFrame(connection, ok(directory.pairingStatus(first)))
                "secure.hello" -> { val (peer, keys) = serverHandshake(connection, first); val request = decryptFrame(keys.receiveKey, keys.sessionId, receiveFrame(connection)); val response = handleSecure(peer, request); sendFrame(connection, encryptFrame(keys.sendKey, keys.sessionId, response)); directory.markConnection(peer.string("host_id")) }
                else -> throw LanException("未知 LAN 协议入口", "lan.protocol_invalid")
            }
        } catch (error: Exception) {
            val failure = error as? LanException ?: LanException("LAN 内部错误", "lan.internal_error", cause = error)
            directory.diagnostic("connection.failed", "warning", errorId = failure.errorId)
            runCatching { sendFrame(connection, failure(failure)) }
        }
    }

    private fun serverHandshake(socket: Socket, hello: JsonObject): Pair<JsonObject, SessionKeys> {
        validateHello(hello); val peer = directory.peer(hello.string("host_id"))
        if (hello.string("public_key") != peer.string("public_key") || !LanCrypto.verify(LanCrypto.unb64(peer.string("public_key")), helloSigningBytes(hello), LanCrypto.unb64(hello.string("signature")))) throw LanException("设备握手签名无效", "lan.authentication_failed")
        val clientNonce = LanCrypto.unb64(hello.string("nonce")); val clientEphemeral = LanCrypto.unb64(hello.string("ephemeral_key")); if (clientNonce.size != 24 || clientEphemeral.size != 32) throw LanException("安全握手字段无效", "lan.protocol_invalid")
        val ephemeral = LanCrypto.generateX25519(); val serverNonce = LanCrypto.random(24)
        val response = JsonObject().apply { addProperty("type", "secure.hello.reply"); addProperty("version", 1); addProperty("host_id", identity.hostId); addProperty("public_key", LanCrypto.b64(identity.publicKey)); addProperty("ephemeral_key", LanCrypto.b64(ephemeral.publicKey)); addProperty("nonce", LanCrypto.b64(serverNonce)); addProperty("client_nonce", LanCrypto.b64(clientNonce)); addProperty("timestamp_ms", System.currentTimeMillis()); addProperty("transcript_hash", LanCrypto.sha256Text(JsonSupport.canonicalBytes(hello))) }
        response.addProperty("signature", LanCrypto.b64(identity.key.sign(helloSigningBytes(response)))); sendFrame(socket, response)
        val shared = ephemeral.exchange(clientEphemeral); val material = keyMaterial(shared, clientNonce, serverNonce, peer.string("host_id"), identity.hostId); val session = sessionId(clientNonce, serverNonce, shared)
        return peer to SessionKeys(material.copyOfRange(32,64), material.copyOfRange(0,32), session)
    }

    private fun clientHandshake(socket: Socket, peer: JsonObject): SessionKeys {
        val ephemeral = LanCrypto.generateX25519(); val nonce = LanCrypto.random(24)
        val hello = JsonObject().apply { addProperty("type", "secure.hello"); addProperty("version", 1); addProperty("host_id", identity.hostId); addProperty("public_key", LanCrypto.b64(identity.publicKey)); addProperty("ephemeral_key", LanCrypto.b64(ephemeral.publicKey)); addProperty("nonce", LanCrypto.b64(nonce)); addProperty("timestamp_ms", System.currentTimeMillis()) }
        hello.addProperty("signature", LanCrypto.b64(identity.key.sign(helloSigningBytes(hello)))); sendFrame(socket, hello)
        val response = receiveFrame(socket); if (response.string("type") != "secure.hello.reply") throw errorFrom(response)
        if (response.string("host_id") != peer.string("host_id") || response.string("public_key") != peer.string("public_key") || response.string("client_nonce") != LanCrypto.b64(nonce) || response.string("transcript_hash") != LanCrypto.sha256Text(JsonSupport.canonicalBytes(hello))) throw LanException("连接设备身份或握手上下文不匹配", "lan.pinned_key_mismatch")
        if (!LanCrypto.verify(LanCrypto.unb64(peer.string("public_key")), helloSigningBytes(response), LanCrypto.unb64(response.string("signature")))) throw LanException("设备握手签名无效", "lan.authentication_failed")
        val serverNonce = LanCrypto.unb64(response.string("nonce")); val remoteEphemeral = LanCrypto.unb64(response.string("ephemeral_key")); val shared = ephemeral.exchange(remoteEphemeral); val material = keyMaterial(shared, nonce, serverNonce, identity.hostId, peer.string("host_id"))
        return SessionKeys(material.copyOfRange(0,32), material.copyOfRange(32,64), sessionId(nonce, serverNonce, shared))
    }

    private fun handleSecure(peer: JsonObject, request: JsonObject): JsonObject {
        val requestId = request.string("request_id"); val type = request.string("request_type"); val timestamp = request.long("timestamp_ms"); val expires = request.long("expires_at_ms"); val now = System.currentTimeMillis(); val payload = request.get("payload")?.takeIf(JsonElement::isJsonObject)?.asJsonObject ?: throw LanException("安全请求正文无效", "lan.protocol_invalid")
        if (requestId.isBlank() || type.isBlank() || timestamp > now + 60_000) throw LanException("安全请求字段无效", "lan.protocol_invalid")
        if (expires <= now || expires - timestamp > MAX_TTL_MS) throw LanException("安全请求已经过期", "lan.request_expired")
        permissionFor(type)?.let { directory.authorize(peer.string("host_id"), it, payload.string("product_id"), payload.string("instance_id")) }
        val hash = LanCrypto.sha256Text(JsonSupport.canonicalBytes(JsonObject().apply { addProperty("request_type", type); add("payload", payload.deepCopy()) }))
        directory.seenResponse(peer.string("host_id"), requestId, hash)?.let { return it }
        val response = try { ok(when (type) { "permissions.query" -> JsonObject().apply { add("permissions", peer.obj("permissions").deepCopy()) }; "status.query" -> statusProvider(); else -> handlers[type]?.invoke(peer, payload) ?: throw LanException("当前宿主没有接入该安全协议处理器", "lan.handler_unavailable", true) }, requestId, type) } catch (error: LanException) { failure(error, requestId, type) }
        directory.rememberResponse(peer.string("host_id"), requestId, hash, response, expires); directory.diagnostic("request.handled", peerHostId = peer.string("host_id"), requestId = requestId, correlationId = payload.string("dispatch_id", payload.string("message_id")), details = JsonObject().apply { addProperty("request_type", type); addProperty("ok", response.bool("ok")) })
        return response
    }

    private fun pairingRequest(type: String, sessionId: String, code: String, payload: JsonObject): JsonObject { val raw = code.uppercase().filter(Char::isLetterOrDigit); val key = LanCrypto.pairingKey(code, sessionId); return JsonObject().apply { addProperty("type", type); addProperty("version", 1); addProperty("session_id", sessionId); addProperty("code_digest", JsonSupport.sha256(raw.toByteArray(Charsets.US_ASCII))); add("payload", payload.deepCopy()); addProperty("mac", LanCrypto.b64(LanCrypto.hmac(key, JsonSupport.canonicalBytes(payload)))) } }
    private fun verifyPairResponse(response: JsonObject, sessionId: String, code: String) { val proof = LanCrypto.unb64(response.string("proof")); val unsigned = response.deepCopy().apply { remove("proof") }; if (!LanCrypto.constantEquals(proof, LanCrypto.hmac(LanCrypto.pairingKey(code, sessionId), JsonSupport.canonicalBytes(unsigned)))) throw LanException("配对应答认证失败", "lan.authentication_failed") }
    private fun plainRequest(address: String, targetPort: Int, request: JsonObject): JsonObject = try { Socket().use { socket -> socket.connect(InetSocketAddress(address, targetPort), 5_000); socket.soTimeout = 10_000; sendFrame(socket, request); val response = receiveFrame(socket); if (!response.bool("ok")) throw errorFrom(response); response.obj("result") } } catch (error: LanException) { throw error } catch (error: Exception) { throw LanException("无法连接配对设备；请检查局域网或地址", "lan.device_unreachable", true, cause = error) }
    private fun validateHello(value: JsonObject) { if (value.int("version") != 1 || kotlin.math.abs(System.currentTimeMillis() - value.long("timestamp_ms")) > 60_000) throw LanException("安全握手已过期或版本不兼容", "lan.handshake_expired") }
    private fun helloSigningBytes(value: JsonObject) = JsonSupport.canonicalBytes(value.deepCopy().apply { remove("signature") })
    private fun keyMaterial(shared: ByteArray, clientNonce: ByteArray, serverNonce: ByteArray, clientHost: String, serverHost: String) = LanCrypto.hkdf(shared, LanCrypto.sha256(clientNonce + serverNonce), "easycode-lan-v6|$clientHost|$serverHost".toByteArray())
    private fun sessionId(clientNonce: ByteArray, serverNonce: ByteArray, shared: ByteArray) = LanCrypto.sha256(clientNonce + serverNonce + shared).joinToString("") { "%02x".format(it) }.take(32)
    private fun encryptFrame(key: ByteArray, sessionId: String, payload: JsonObject): JsonObject { val nonce = LanCrypto.sha256("$sessionId:nonce".toByteArray()).copyOfRange(0,4) + ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN).putLong(1).array(); val aad = "easycode-lan-v6|$sessionId|1".toByteArray(Charsets.US_ASCII); return JsonObject().apply { addProperty("type", "secure.frame"); addProperty("session_id", sessionId); addProperty("sequence", 1); addProperty("ciphertext", LanCrypto.b64(LanCrypto.encrypt(key, nonce, aad, JsonSupport.canonicalBytes(payload)))) } }
    private fun decryptFrame(key: ByteArray, sessionId: String, frame: JsonObject): JsonObject { if (frame.string("type") != "secure.frame" || frame.string("session_id") != sessionId || frame.int("sequence") != 1) throw LanException("安全帧序号或会话无效", "lan.replay_detected"); val nonce = LanCrypto.sha256("$sessionId:nonce".toByteArray()).copyOfRange(0,4) + ByteBuffer.allocate(8).order(ByteOrder.BIG_ENDIAN).putLong(1).array(); return JsonSupport.parseObject(LanCrypto.decrypt(key, nonce, "easycode-lan-v6|$sessionId|1".toByteArray(Charsets.US_ASCII), LanCrypto.unb64(frame.string("ciphertext"))), "安全帧正文") }
    private fun sendFrame(socket: Socket, value: JsonObject) { val data = JsonSupport.canonicalBytes(value); if (data.size > MAX_FRAME) throw LanException("LAN 帧超过大小限制", "lan.frame_too_large"); DataOutputStream(socket.getOutputStream()).apply { writeInt(data.size); write(data); flush() } }
    private fun receiveFrame(socket: Socket): JsonObject { val input = DataInputStream(socket.getInputStream()); val size = input.readInt(); if (size !in 1..MAX_FRAME) throw LanException("LAN 帧长度无效", "lan.protocol_invalid"); val bytes = ByteArray(size); input.readFully(bytes); return JsonSupport.parseObject(bytes, "LAN 帧") }
    private fun ok(result: JsonObject, requestId: String = "", type: String = "") = JsonObject().apply { addProperty("ok", true); if (requestId.isNotBlank()) addProperty("request_id", requestId); if (type.isNotBlank()) addProperty("request_type", type); add("result", result.deepCopy()); if (requestId.isNotBlank()) addProperty("responded_at_ms", System.currentTimeMillis()) }
    private fun failure(error: LanException, requestId: String = "", type: String = "") = JsonObject().apply { addProperty("ok", false); if (requestId.isNotBlank()) addProperty("request_id", requestId); if (type.isNotBlank()) addProperty("request_type", type); add("error", JsonObject().apply { addProperty("error_id", error.errorId); addProperty("message", error.message); addProperty("transient", error.transient); addProperty("action", error.action) }); if (requestId.isNotBlank()) addProperty("responded_at_ms", System.currentTimeMillis()) }
    private fun errorFrom(value: JsonObject): LanException { val raw = value.obj("error"); return LanException(raw.string("message", "LAN 请求失败"), raw.string("error_id", "lan.request_failed"), raw.bool("transient"), raw.string("action", "retry")) }
    private fun permissionFor(type: String): String? = when { type == "permissions.query" -> null; type.startsWith("message.") -> "messages"; type in setOf("status.query","dispatch.status") -> "status"; type == "dispatch.start" -> "remote_start"; else -> throw LanException("安全通道请求类型未知", "lan.request_unknown") }
    private fun id(prefix: String) = "${prefix}_${UUID.randomUUID().toString().replace("-", "")}" 
    private data class SessionKeys(val sendKey: ByteArray, val receiveKey: ByteArray, val sessionId: String)

    companion object { private const val DISCOVERY_MAGIC = "easycode.lan.discovery.v6"; private const val MAX_FRAME = 2 * 1024 * 1024; private const val MAX_TTL_MS = 7L * 24 * 60 * 60 * 1000 }
}
