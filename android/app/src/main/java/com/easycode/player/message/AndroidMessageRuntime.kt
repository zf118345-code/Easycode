package com.easycode.player.message

import android.content.Context
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.lan.AndroidLanControl
import com.easycode.player.lan.LanException
import com.easycode.player.profile.ProfileStore
import com.easycode.player.runtime.RuntimeControl
import com.easycode.player.runtime.RuntimeFailure
import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.bool
import com.easycode.player.util.JsonSupport.long
import com.easycode.player.util.JsonSupport.obj
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonArray
import com.google.gson.JsonElement
import com.google.gson.JsonNull
import com.google.gson.JsonObject
import java.io.File
import java.time.Instant
import com.easycode.player.util.Base64Codec
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

internal class AndroidMessageRuntime(
    private val context: Context,
    private val profiles: ProfileStore,
    private val bundleProvider: () -> VerifiedBundle,
    private val lan: AndroidLanControl,
) {
    private val locks = ConcurrentHashMap<String, Any>()

    init {
        lan.registerHandler("message.offer", ::handleOffer)
        lan.registerHandler("message.status", ::handleStatus)
        lan.registerHandler("message.cancel", ::handleCancel)
        lan.registerTickHandler { runCatching { flush(bundleProvider()) } }
        lan.setStatusProvider(::statusCatalog)
    }

    fun instance(bundle: VerifiedBundle): JsonObject = synchronized(lock(bundle)) {
        val document = read(bundle); val item = document.obj("instance")
        if (item.string("instance_id").isNotBlank()) return@synchronized instanceResult(bundle, item)
        val created = JsonObject().apply {
            addProperty("instance_id", id("instance")); addProperty("display_name", "实例1")
            addProperty("created_at", Instant.now().toString()); addProperty("updated_at", Instant.now().toString())
        }
        document.add("instance", created); write(bundle, document); instanceResult(bundle, created)
    }

    fun renameInstance(bundle: VerifiedBundle, name: String): JsonObject = synchronized(lock(bundle)) {
        val clean = name.trim(); if (clean.isBlank() || clean.length > 160 || clean.any { it.code < 32 }) fail("实例名称必须为 1-160 个字符", "message.instance_invalid")
        val document = read(bundle); val item = document.obj("instance"); if (item.string("instance_id").isBlank()) instance(bundle)
        val latest = read(bundle); latest.obj("instance").apply { addProperty("display_name", clean); addProperty("updated_at", Instant.now().toString()) }; write(bundle, latest); instanceResult(bundle, latest.obj("instance"))
    }

    fun status(bundle: VerifiedBundle): JsonObject = synchronized(lock(bundle)) {
        val document = read(bundle); if (maintain(document)) write(bundle, document)
        JsonObject().apply {
            add("instance", instance(bundle)); add("batches", JsonArray().apply {
                document.array("batches").sortedByDescending { it.asJsonObject.long("created_at_ms") }.take(200).forEach { add(redactedBatch(it.asJsonObject)) }
            }); add("copies", JsonArray().apply {
                document.array("copies").sortedByDescending { it.asJsonObject.long("created_at_ms") }.take(200).forEach { raw -> add(redactedCopy(raw.asJsonObject)) }
            })
        }
    }

    fun send(bundle: VerifiedBundle, recipientsValue: Any?, nameValue: Any?, contentValue: Any?, ttlMs: Long): Map<String, Any?> {
        val name = validateName(nameValue); if (ttlMs !in 1..MAX_TTL) fail("消息有效期超出允许范围", "message.content_invalid")
        val content = validatedContent(JsonSupport.fromAny(contentValue)); val encoded = JsonSupport.canonicalBytes(content); if (encoded.size > MAX_CONTENT) fail("消息内容超过 256 KiB", "message.content_invalid")
        val rawRecipients = recipientsValue as? List<*> ?: fail("接收实例必须是列表", "message.instance_unknown")
        if (rawRecipients.isEmpty() || rawRecipients.size > 64) fail("接收实例数量必须为 1-64", "message.instance_unknown")
        val recipients = rawRecipients.map(::referenceParts); if (recipients.distinct().size != recipients.size) fail("接收实例不能重复", "message.instance_unknown")
        val sender = instance(bundle); val now = System.currentTimeMillis(); val batchId = id("batch")
        synchronized(lock(bundle)) {
            val document = read(bundle); val copies = JsonArray()
            val remote = lan.status().array("remote_instances")
            recipients.forEachIndexed { index, pair ->
                val local = pair.first == lan.identity.hostId && pair.second == sender.string("instance_id")
                val remoteEntry = remote.firstOrNull { it.isJsonObject && it.asJsonObject.string("host_id") == pair.first && it.asJsonObject.string("instance_id") == pair.second && it.asJsonObject.string("project_namespace") == bundle.productId }?.asJsonObject
                if (!local && remoteEntry == null) fail("接收实例未知、未配对或未刷新", "message.instance_unknown")
                copies.add(JsonObject().apply {
                    addProperty("message_id", "message_${batchId}_${index + 1}"); addProperty("batch_id", batchId); addProperty("project_namespace", bundle.productId)
                    addProperty("recipient_host_id", pair.first); addProperty("recipient_instance_id", pair.second); addProperty("recipient_display_name", if (local) sender.string("display_name") else remoteEntry!!.string("display_name", pair.second))
                    addProperty("status", if (local) "waiting_read" else "waiting_send"); addProperty("transport_kind", if (local) "local" else "lan")
                    addProperty("created_at_ms", now); addProperty("expires_at_ms", now + ttlMs); addProperty("remote_accepted_at_ms", 0L); addProperty("read_at_ms", 0L); addProperty("cancelled_at_ms", 0L); addProperty("cancel_requested", false); addProperty("transport_error", "")
                })
            }
            val batch = JsonObject().apply {
                addProperty("batch_id", batchId); addProperty("project_namespace", bundle.productId); addProperty("sender_host_id", lan.identity.hostId); addProperty("sender_instance_id", sender.string("instance_id")); addProperty("sender_display_name", sender.string("display_name")); addProperty("name", name); add("content", content.deepCopy()); addProperty("content_hash", "sha256:" + JsonSupport.sha256(encoded)); addProperty("created_at_ms", now); addProperty("expires_at_ms", now + ttlMs)
            }
            document.array("batches").add(batch); copies.forEach { document.array("copies").add(it) }; write(bundle, document)
        }
        flush(bundle, batchId)
        return JsonSupport.toAny(batchResult(bundle, batchId)) as Map<String, Any?>
    }

    fun waitReceive(bundle: VerifiedBundle, nameValue: Any?, senderValue: Any?, timeoutMs: Long, control: RuntimeControl): Map<String, Any?>? {
        val name = validateName(nameValue); val sender = senderValue?.let(::referenceParts); val deadline = System.nanoTime() + timeoutMs.coerceIn(0, MAX_TTL) * 1_000_000
        while (true) {
            control.checkpoint()
            claim(bundle, name, sender)?.let { return JsonSupport.toAny(it) as Map<String, Any?> }
            if (System.nanoTime() >= deadline) return null
            control.sleep(50)
        }
    }

    fun peek(bundle: VerifiedBundle, nameValue: Any?, senderValue: Any?): JsonObject? {
        val name = validateName(nameValue); val sender = senderValue?.let(::referenceParts); val receiver = instance(bundle)
        return synchronized(lock(bundle)) {
            val document = read(bundle); if (maintain(document)) write(bundle, document)
            val batches = document.array("batches").associateBy { it.asJsonObject.string("batch_id") }
            document.array("copies").firstOrNull { raw ->
                val copy = raw.asJsonObject; val batch = batches[copy.string("batch_id")]?.asJsonObject
                copy.string("recipient_host_id") == lan.identity.hostId && copy.string("recipient_instance_id") == receiver.string("instance_id") && copy.string("status") == "waiting_read" && batch?.string("name") == name && (sender == null || (batch.string("sender_host_id") == sender.first && batch.string("sender_instance_id") == sender.second))
            }?.asJsonObject?.let { decoded(document, it) }
        }
    }

    fun snapshotCandidates(bundle: VerifiedBundle, nameValue: Any?, senderValue: Any?): List<JsonObject> {
        val name = validateName(nameValue); val sender = senderValue?.let(::referenceParts); val receiver = instance(bundle)
        return synchronized(lock(bundle)) {
            val document = read(bundle); if (maintain(document)) write(bundle, document); val batches = document.array("batches").associateBy { it.asJsonObject.string("batch_id") }
            document.array("copies").filter { raw ->
                val copy = raw.asJsonObject; val batch = batches[copy.string("batch_id")]?.asJsonObject
                copy.string("recipient_host_id") == lan.identity.hostId && copy.string("recipient_instance_id") == receiver.string("instance_id") && copy.string("status") == "waiting_read" && batch?.string("name") == name && (sender == null || batch.string("sender_host_id") == sender.first && batch.string("sender_instance_id") == sender.second)
            }.map { decoded(document, it.asJsonObject) }
        }
    }

    fun claimById(bundle: VerifiedBundle, messageId: String): JsonObject? = synchronized(lock(bundle)) {
        val receiver = instance(bundle); val document = read(bundle); maintain(document)
        val copy = document.array("copies").firstOrNull { it.isJsonObject && it.asJsonObject.string("message_id") == messageId && it.asJsonObject.string("recipient_host_id") == lan.identity.hostId && it.asJsonObject.string("recipient_instance_id") == receiver.string("instance_id") && it.asJsonObject.string("status") == "waiting_read" }?.asJsonObject ?: return@synchronized null
        val result = decoded(document, copy); val read = System.currentTimeMillis(); copy.addProperty("status", "read"); copy.addProperty("read_at_ms", read); write(bundle, document); result.apply { addProperty("read_at", Instant.ofEpochMilli(read).toString()) }
    }

    fun waitRead(bundle: VerifiedBundle, batchValue: Any?, modeValue: Any?, timeoutMs: Long, control: RuntimeControl): Map<String, Any?> {
        val batchId = batchId(batchValue); val mode = modeValue?.toString().orEmpty().ifBlank { "all" }; if (mode !in setOf("all","any")) fail("等待方式只能是全部或任一", "message.content_invalid")
        val deadline = System.nanoTime() + timeoutMs.coerceIn(0, MAX_TTL) * 1_000_000
        while (true) {
            control.checkpoint(); flush(bundle, batchId); val result = waitReadResult(bundle, batchId, mode)
            if (result.bool("condition_met") || result.bool("terminal") || System.nanoTime() >= deadline) return JsonSupport.toAny(result) as Map<String, Any?>
            control.sleep(50)
        }
    }

    fun cancel(bundle: VerifiedBundle, batchValue: Any?, recipientValue: Any?): Map<String, Any?> {
        val batchId = batchId(batchValue); val recipient = recipientValue?.let(::referenceParts)
        synchronized(lock(bundle)) {
            val document = read(bundle); requireOwnedBatch(bundle, document, batchId); maintain(document)
            val selected = document.array("copies").filter { raw -> val copy = raw.asJsonObject; copy.string("batch_id") == batchId && (recipient == null || copy.string("recipient_host_id") == recipient.first && copy.string("recipient_instance_id") == recipient.second) }
            if (selected.isEmpty()) fail("指定实例不属于此发送批次", "message.instance_unknown")
            selected.forEach { raw -> val copy = raw.asJsonObject; if (copy.string("transport_kind") == "local" && copy.string("status") == "waiting_read") { copy.addProperty("status", "cancelled"); copy.addProperty("cancelled_at_ms", System.currentTimeMillis()) } else if (copy.string("transport_kind") == "lan" && copy.string("status") in setOf("waiting_send","waiting_read")) copy.addProperty("cancel_requested", true) }
            write(bundle, document)
        }
        flush(bundle, batchId)
        val details = batchCopies(bundle, batchId, recipient); val cancelled = details.filter { it.string("status") == "cancelled" }.map { reference(it.string("recipient_host_id"), it.string("recipient_instance_id")) }; val notCancelled = details.filter { it.string("status") != "cancelled" }.map { reference(it.string("recipient_host_id"), it.string("recipient_instance_id")) }
        return JsonSupport.toAny(JsonObject().apply { addProperty("batch_id", batchId); add("cancelled_instances", JsonSupport.fromAny(cancelled)); add("not_cancelled_instances", JsonSupport.fromAny(notCancelled)); add("recipients", JsonArray().apply { details.forEach { add(copyResult(it)) } }) }) as Map<String, Any?>
    }

    fun execute(bundle: VerifiedBundle, opcode: String, functionId: String, arguments: Map<String, Any?>, control: RuntimeControl): Any? {
        fun argument(name: String, fallback: String, default: Any? = null): Any? = arguments["$functionId.parameter.$name"] ?: arguments[fallback] ?: default
        return try {
            when (opcode) {
                "message.send" -> send(bundle, argument("recipients", "接收实例"), argument("name", "消息名称"), argument("content", "内容"), duration(argument("ttl", "有效期"), 300_000))
                "message.wait_receive" -> waitReceive(bundle, argument("name", "消息名称"), argument("sender", "来源实例"), duration(argument("timeout", "超时"), 60_000), control)
                "message.wait_read" -> waitRead(bundle, argument("batch", "发送批次"), argument("mode", "等待方式", "all"), duration(argument("timeout", "超时"), 60_000), control)
                "message.cancel" -> cancel(bundle, argument("batch", "发送批次"), argument("recipient", "接收实例"))
                else -> fail("Android 消息运行器不支持 $opcode", "message.transport_unavailable")
            }
        } catch (error: MessageException) { throw RuntimeFailure(error.errorId, error.message.orEmpty(), transient = error.transient, cause = error) }
    }

    fun flush(bundle: VerifiedBundle, batchId: String = ""): JsonObject {
        val candidates = synchronized(lock(bundle)) {
            val document = read(bundle); if (maintain(document)) write(bundle, document)
            document.array("copies").filter { raw -> val copy = raw.asJsonObject; copy.string("transport_kind") == "lan" && copy.string("status") in setOf("waiting_send","waiting_read") && (batchId.isBlank() || copy.string("batch_id") == batchId) }.map { it.asJsonObject.deepCopy() }
        }
        var delivered = 0; var deferred = 0; var failed = 0
        candidates.forEach { copy ->
            val remaining = copy.long("expires_at_ms") - System.currentTimeMillis(); if (remaining <= 0) return@forEach
            try {
                val result = when {
                    copy.bool("cancel_requested") -> lan.secureRequest(copy.string("recipient_host_id"), "message.cancel", JsonObject().apply { addProperty("message_id", copy.string("message_id")) }, "cancel_${copy.string("message_id")}", remaining)
                    copy.long("remote_accepted_at_ms") == 0L -> offer(bundle, copy, remaining)
                    else -> lan.secureRequest(copy.string("recipient_host_id"), "message.status", JsonObject().apply { addProperty("message_id", copy.string("message_id")) }, ttlMs = minOf(30_000, remaining))
                }
                applyRemote(bundle, copy.string("message_id"), result); delivered++
            } catch (error: LanException) { recordTransportError(bundle, copy.string("message_id"), error); if (error.transient) deferred++ else failed++ }
        }
        return JsonObject().apply { addProperty("attempted", candidates.size); addProperty("delivered", delivered); addProperty("deferred", deferred); addProperty("failed", failed) }
    }

    private fun offer(bundle: VerifiedBundle, copy: JsonObject, ttl: Long): JsonObject {
        val document = synchronized(lock(bundle)) { read(bundle) }; val batch = document.array("batches").first { it.asJsonObject.string("batch_id") == copy.string("batch_id") }.asJsonObject
        return lan.secureRequest(copy.string("recipient_host_id"), "message.offer", JsonObject().apply {
            listOf("message_id","batch_id","project_namespace","recipient_host_id","recipient_instance_id").forEach { addProperty(it, copy.string(it)) }
            listOf("sender_host_id","sender_instance_id","sender_display_name","name","content_hash").forEach { addProperty(it, batch.string(it)) }
            add("content", batch.get("content").deepCopy()); addProperty("created_at_ms", batch.long("created_at_ms")); addProperty("expires_at_ms", batch.long("expires_at_ms"))
        }, "offer_${copy.string("message_id")}", ttl)
    }

    private fun handleOffer(peer: JsonObject, payload: JsonObject): JsonObject {
        val bundle = bundleProvider(); if (payload.string("project_namespace") != bundle.productId || payload.string("sender_host_id") != peer.string("host_id") || payload.string("recipient_host_id") != lan.identity.hostId) throw LanException("消息项目或设备身份不匹配", "message.instance_unknown")
        val local = instance(bundle); if (payload.string("recipient_instance_id") != local.string("instance_id")) throw LanException("已授权接收实例当前未登记", "message.transport_unavailable", true)
        val messageId = payload.string("message_id"); val batchId = payload.string("batch_id"); val name = payload.string("name").trim()
        val createdAt = payload.long("created_at_ms"); val expiresAt = payload.long("expires_at_ms"); val now = System.currentTimeMillis()
        if (messageId.isBlank() || batchId.isBlank() || name.isBlank() || name.length > 160 || name.any { it.code < 32 }) throw LanException("消息标识或名称无效", "message.content_invalid")
        if (createdAt <= 0 || expiresAt <= createdAt || expiresAt - createdAt > MAX_TTL || createdAt > now + 60_000) throw LanException("消息时间或有效期无效", "message.content_invalid")
        val content = try { validatedContent(payload.get("content") ?: JsonNull.INSTANCE) } catch (error: MessageException) { throw LanException(error.message.orEmpty(), error.errorId) }
        val encoded = JsonSupport.canonicalBytes(content); if (encoded.size > MAX_CONTENT) throw LanException("消息内容超过 256 KiB", "message.content_invalid")
        if ("sha256:" + JsonSupport.sha256(encoded) != payload.string("content_hash")) throw LanException("消息内容摘要不匹配", "message.decode_failed")
        synchronized(lock(bundle)) {
            val document = read(bundle); val batches = document.array("batches"); val copies = document.array("copies")
            val existing = copies.firstOrNull { it.isJsonObject && it.asJsonObject.string("message_id") == messageId }?.asJsonObject
            if (existing == null) {
                val existingBatch = batches.firstOrNull { it.isJsonObject && it.asJsonObject.string("batch_id") == batchId }?.asJsonObject
                if (existingBatch == null) batches.add(JsonObject().apply { listOf("batch_id","project_namespace","sender_host_id","sender_instance_id","sender_display_name","name","content_hash").forEach { addProperty(it, payload.string(it)) }; add("content", content.deepCopy()); addProperty("created_at_ms", createdAt); addProperty("expires_at_ms", expiresAt) })
                else if (existingBatch.string("content_hash") != payload.string("content_hash") || existingBatch.string("sender_host_id") != peer.string("host_id")) throw LanException("相同批次 ID 的内容不一致", "message.idempotency_conflict")
                copies.add(JsonObject().apply { listOf("message_id","batch_id","project_namespace","recipient_host_id","recipient_instance_id").forEach { addProperty(it, payload.string(it)) }; addProperty("recipient_display_name", local.string("display_name")); addProperty("status", if (expiresAt <= now) "expired" else "waiting_read"); addProperty("transport_kind", "lan_inbound"); addProperty("created_at_ms", createdAt); addProperty("expires_at_ms", expiresAt); addProperty("read_at_ms", 0L); addProperty("cancelled_at_ms", 0L) })
            } else if (existing.string("batch_id") != batchId || existing.string("recipient_instance_id") != local.string("instance_id")) throw LanException("相同消息 ID 已用于不同副本", "message.idempotency_conflict")
            maintain(document); write(bundle, document)
        }
        return wireStatus(bundle, messageId)
    }

    private fun handleStatus(peer: JsonObject, payload: JsonObject): JsonObject = inboundOwned(bundleProvider(), peer, payload, cancel = false)
    private fun handleCancel(peer: JsonObject, payload: JsonObject): JsonObject = inboundOwned(bundleProvider(), peer, payload, cancel = true)
    private fun inboundOwned(bundle: VerifiedBundle, peer: JsonObject, payload: JsonObject, cancel: Boolean): JsonObject = synchronized(lock(bundle)) {
        val document = read(bundle); val changed = maintain(document); val batchById = document.array("batches").associateBy { it.asJsonObject.string("batch_id") }
        val copy = document.array("copies").firstOrNull { raw -> val c = raw.asJsonObject; val batch = batchById[c.string("batch_id")]?.asJsonObject; c.string("message_id") == payload.string("message_id") && batch?.string("sender_host_id") == peer.string("host_id") }?.asJsonObject ?: throw LanException("消息副本不存在或不属于认证设备", "message.instance_unknown")
        var mutated = changed
        if (cancel && copy.string("status") == "waiting_read") { copy.addProperty("status", "cancelled"); copy.addProperty("cancelled_at_ms", System.currentTimeMillis()); mutated = true }
        if (mutated) write(bundle, document); wireStatus(copy)
    }

    private fun claim(bundle: VerifiedBundle, name: String, sender: Pair<String,String>?): JsonObject? { val found = peek(bundle, name, sender?.let { reference(it.first,it.second) }) ?: return null; return claimById(bundle, found.string("message_id")) }
    private fun decoded(document: JsonObject, copy: JsonObject): JsonObject { val batch = document.array("batches").first { it.asJsonObject.string("batch_id") == copy.string("batch_id") }.asJsonObject; return JsonObject().apply { addProperty("record_type", "received_message"); addProperty("message_id", copy.string("message_id")); addProperty("batch_id", copy.string("batch_id")); addProperty("name", batch.string("name")); add("content", batch.get("content").deepCopy()); add("sender", JsonSupport.fromAny(reference(batch.string("sender_host_id"), batch.string("sender_instance_id")))); addProperty("sender_display_name", batch.string("sender_display_name")); addProperty("created_at", Instant.ofEpochMilli(batch.long("created_at_ms")).toString()); addProperty("expires_at", Instant.ofEpochMilli(batch.long("expires_at_ms")).toString()) } }
    private fun waitReadResult(bundle: VerifiedBundle, batchId: String, mode: String): JsonObject = synchronized(lock(bundle)) { val document = read(bundle); requireOwnedBatch(bundle, document, batchId); if (maintain(document)) write(bundle, document); val rows = document.array("copies").filter { it.asJsonObject.string("batch_id") == batchId }.map { it.asJsonObject }; val groups = mapOf("read_instances" to "read", "expired_instances" to "expired", "failed_instances" to "failed", "cancelled_instances" to "cancelled"); JsonObject().apply { addProperty("batch_id", batchId); addProperty("mode", mode); groups.forEach { (key,status) -> add(key, JsonSupport.fromAny(rows.filter { it.string("status") == status }.map { reference(it.string("recipient_host_id"), it.string("recipient_instance_id")) })) }; val unread = rows.filter { it.string("status") in setOf("waiting_send","waiting_read") }; add("unread_instances", JsonSupport.fromAny(unread.map { reference(it.string("recipient_host_id"), it.string("recipient_instance_id")) })); val read = rows.count { it.string("status") == "read" }; addProperty("condition_met", if (mode == "any") read > 0 else rows.isNotEmpty() && read == rows.size); addProperty("terminal", unread.isEmpty()) } }
    private fun batchResult(bundle: VerifiedBundle, batchId: String): JsonObject = synchronized(lock(bundle)) { val document = read(bundle); val batch = document.array("batches").firstOrNull { it.asJsonObject.string("batch_id") == batchId }?.asJsonObject ?: fail("发送批次不存在", "message.batch_unknown"); JsonObject().apply { addProperty("batch_id", batchId); addProperty("name", batch.string("name")); addProperty("created_at", Instant.ofEpochMilli(batch.long("created_at_ms")).toString()); addProperty("expires_at", Instant.ofEpochMilli(batch.long("expires_at_ms")).toString()); add("recipients", JsonArray().apply { document.array("copies").filter { it.asJsonObject.string("batch_id") == batchId }.forEach { add(copyResult(it.asJsonObject)) } }) } }
    private fun copyResult(copy: JsonObject): JsonObject = JsonObject().apply { addProperty("message_id", copy.string("message_id")); add("recipient", JsonSupport.fromAny(reference(copy.string("recipient_host_id"), copy.string("recipient_instance_id")))); addProperty("recipient_display_name", copy.string("recipient_display_name")); addProperty("status", copy.string("status")); addProperty("transport", copy.string("transport_kind")); addProperty("transport_error", copy.string("transport_error")); addProperty("created_at", Instant.ofEpochMilli(copy.long("created_at_ms")).toString()); addProperty("expires_at", Instant.ofEpochMilli(copy.long("expires_at_ms")).toString()) }
    private fun wireStatus(bundle: VerifiedBundle, messageId: String): JsonObject = synchronized(lock(bundle)) { val document = read(bundle); if (maintain(document)) write(bundle, document); val copy = document.array("copies").firstOrNull { it.asJsonObject.string("message_id") == messageId }?.asJsonObject ?: throw LanException("消息不存在", "message.instance_unknown"); wireStatus(copy) }
    private fun wireStatus(copy: JsonObject) = JsonObject().apply { addProperty("message_id", copy.string("message_id")); addProperty("batch_id", copy.string("batch_id")); addProperty("status", copy.string("status")); add("read_at_ms", copy.long("read_at_ms").takeIf { it > 0 }?.let(JsonSupport::fromAny) ?: JsonNull.INSTANCE); add("cancelled_at_ms", copy.long("cancelled_at_ms").takeIf { it > 0 }?.let(JsonSupport::fromAny) ?: JsonNull.INSTANCE); addProperty("failure_code", copy.string("failure_code")); addProperty("expires_at_ms", copy.long("expires_at_ms")) }
    private fun applyRemote(bundle: VerifiedBundle, messageId: String, result: JsonObject) = synchronized(lock(bundle)) { val document = read(bundle); val copy = document.array("copies").firstOrNull { it.asJsonObject.string("message_id") == messageId }?.asJsonObject ?: return@synchronized; copy.addProperty("status", result.string("status").takeIf { it in setOf("waiting_read","read","expired","cancelled","failed") } ?: "failed"); copy.addProperty("read_at_ms", result.long("read_at_ms")); copy.addProperty("cancelled_at_ms", result.long("cancelled_at_ms")); copy.addProperty("failure_code", result.string("failure_code")); copy.addProperty("remote_accepted_at_ms", System.currentTimeMillis()); copy.addProperty("transport_error", ""); write(bundle, document) }
    private fun recordTransportError(bundle: VerifiedBundle, messageId: String, error: LanException) = synchronized(lock(bundle)) { val document = read(bundle); val copy = document.array("copies").firstOrNull { it.asJsonObject.string("message_id") == messageId }?.asJsonObject ?: return@synchronized; copy.addProperty("transport_error", error.errorId); if (!error.transient && error.errorId !in setOf("lan.device_unreachable","lan.connection_interrupted","lan.handler_unavailable")) { copy.addProperty("status", "failed"); copy.addProperty("failure_code", error.errorId) }; write(bundle, document) }
    private fun batchCopies(bundle: VerifiedBundle, batchId: String, recipient: Pair<String,String>?): List<JsonObject> = synchronized(lock(bundle)) { read(bundle).array("copies").filter { val copy = it.asJsonObject; copy.string("batch_id") == batchId && (recipient == null || copy.string("recipient_host_id") == recipient.first && copy.string("recipient_instance_id") == recipient.second) }.map { it.asJsonObject.deepCopy() } }
    private fun requireOwnedBatch(bundle: VerifiedBundle, document: JsonObject, batchId: String): JsonObject { val sender = instance(bundle); return document.array("batches").firstOrNull { val b=it.asJsonObject; b.string("batch_id") == batchId && b.string("sender_host_id") == lan.identity.hostId && b.string("sender_instance_id") == sender.string("instance_id") }?.asJsonObject ?: fail("发送批次不存在或不属于当前实例", "message.batch_unknown") }
    private fun maintain(document: JsonObject): Boolean {
        val now = System.currentTimeMillis(); var changed = false
        document.array("copies").filter(JsonElement::isJsonObject).map(JsonElement::getAsJsonObject).filter { it.string("status") in setOf("waiting_send","waiting_read") && it.long("expires_at_ms") <= now }.forEach { it.addProperty("status", "expired"); changed = true }
        val copies = document.array("copies"); val removable = mutableSetOf<String>()
        for (index in copies.size() - 1 downTo 0) { val copy = copies[index].asJsonObject; if (copy.string("status") in setOf("read","expired","cancelled","failed") && copy.long("expires_at_ms") < now - RETENTION_MS) { removable += copy.string("batch_id"); copies.remove(index); changed = true } }
        if (removable.isNotEmpty()) { val remaining = copies.map { it.asJsonObject.string("batch_id") }.toSet(); val batches = document.array("batches"); for (index in batches.size() - 1 downTo 0) if (batches[index].asJsonObject.string("batch_id") in removable && batches[index].asJsonObject.string("batch_id") !in remaining) { batches.remove(index); changed = true } }
        return changed
    }
    private fun redactedBatch(batch: JsonObject) = JsonObject().apply { listOf("batch_id","project_namespace","sender_host_id","sender_instance_id","sender_display_name","name").forEach { addProperty(it, batch.string(it)) }; addProperty("created_at", Instant.ofEpochMilli(batch.long("created_at_ms")).toString()); addProperty("expires_at", Instant.ofEpochMilli(batch.long("expires_at_ms")).toString()) }
    private fun redactedCopy(copy: JsonObject) = JsonObject().apply { listOf("message_id","batch_id","recipient_host_id","recipient_instance_id","recipient_display_name","status","transport_kind","transport_error").forEach { addProperty(it, copy.string(it)) }; addProperty("created_at", Instant.ofEpochMilli(copy.long("created_at_ms")).toString()); addProperty("expires_at", Instant.ofEpochMilli(copy.long("expires_at_ms")).toString()) }
    private fun statusCatalog(): JsonObject = runCatching { val bundle = bundleProvider(); val item = instance(bundle); JsonObject().apply { add("instances", JsonArray().apply { add(JsonObject().apply { addProperty("project_namespace", bundle.productId); addProperty("host_id", lan.identity.hostId); addProperty("instance_id", item.string("instance_id")); addProperty("display_name", item.string("display_name")); addProperty("product_id", bundle.productId); add("profiles", JsonSupport.fromAny(profiles.list(bundle).map { mapOf("profile_id" to it.profileId, "name" to it.name, "revision" to it.revision) })); addProperty("status", "online") }) }) } }.getOrElse { JsonObject().apply { add("instances", JsonArray()) } }
    private fun instanceResult(bundle: VerifiedBundle, value: JsonObject) = JsonObject().apply { addProperty("project_namespace", bundle.productId); addProperty("host_id", lan.identity.hostId); addProperty("instance_id", value.string("instance_id")); addProperty("display_name", value.string("display_name")); add("reference", JsonSupport.fromAny(reference(lan.identity.hostId, value.string("instance_id")))) }
    private fun reference(host: String, instance: String) = mapOf("kind" to "entity_ref", "reference_type" to "instance_ref", "reference_id" to "instance_ref.v1.${encode(host)}.${encode(instance)}")
    private fun referenceParts(value: Any?): Pair<String,String> { val map = value as? Map<*,*> ?: fail("实例引用无效", "message.instance_unknown"); if (map["kind"]?.toString()?.takeIf(String::isNotBlank)?.let { it != "entity_ref" } == true || map["reference_type"]?.toString()?.takeIf(String::isNotBlank)?.let { it != "instance_ref" } == true) fail("引用不是运行实例", "message.instance_unknown"); var host = map["host_id"]?.toString().orEmpty(); var instance = map["instance_id"]?.toString().orEmpty(); val id = map["reference_id"]?.toString().orEmpty(); if ((host.isBlank() || instance.isBlank()) && id.startsWith("instance_ref.v1.")) { val parts=id.split('.', limit=4); if(parts.size==4){host=decode(parts[2]);instance=decode(parts[3])} }; if(host.isBlank()||instance.isBlank()) fail("实例引用缺少稳定身份", "message.instance_unknown"); return host to instance }
    private fun validateName(value: Any?) = value?.toString()?.trim()?.takeIf { it.isNotBlank() && it.length <= 160 && it.none { ch -> ch.code < 32 } } ?: fail("消息名称不能为空", "message.content_invalid")
    private fun validatedContent(value: JsonElement, depth: Int = 0, count: IntArray = intArrayOf(0)): JsonElement { count[0]++; if(depth>64||count[0]>10_000) fail("消息内容层级或项目数量超过限制", "message.content_invalid"); when { value.isJsonNull || value.isJsonPrimitive -> { if(value.isJsonPrimitive && value.asJsonPrimitive.isNumber && !value.asDouble.isFinite()) fail("消息不能包含无穷数", "message.content_invalid") }; value.isJsonArray -> value.asJsonArray.forEach { validatedContent(it,depth+1,count) }; value.isJsonObject -> value.asJsonObject.entrySet().forEach { validatedContent(it.value,depth+1,count) }; else -> fail("消息内容类型无效", "message.content_invalid") }; return value.deepCopy() }
    private fun duration(value: Any?, default: Long) = when(value){ null->default; is Number->value.toLong(); is Map<*,*>->(value["milliseconds"] as? Number)?.toLong() ?: default; else->fail("持续时间无效", "message.content_invalid") }
    private fun batchId(value: Any?) = (value as? Map<*,*>)?.get("batch_id")?.toString()?.takeIf(String::isNotBlank) ?: fail("发送批次无效", "message.batch_unknown")
    private fun read(bundle: VerifiedBundle): JsonObject { val file=file(bundle); if(!file.isFile) return JsonObject().apply { addProperty("schema_version",1); add("instance",JsonObject()); add("batches",JsonArray()); add("copies",JsonArray()) }; return runCatching { JsonSupport.parseObject(file.readBytes(),"消息队列") }.getOrElse { fail("消息队列损坏", "message.transport_unavailable", cause=it) }.also { if(it.long("schema_version")!=1L) fail("消息队列版本不兼容", "message.transport_unavailable") } }
    private fun write(bundle: VerifiedBundle, value: JsonObject) = AtomicFiles.write(file(bundle), JsonSupport.canonicalBytes(value))
    private fun file(bundle: VerifiedBundle) = File(context.filesDir,"player-data/${JsonSupport.sha256(bundle.productId.toByteArray())}/messages.json")
    private fun lock(bundle: VerifiedBundle)=locks.computeIfAbsent(bundle.productId){Any()}
    private fun encode(value:String)=Base64Codec.encode(value.toByteArray(), urlSafe = true, padded = false)
    private fun decode(value:String)=String(Base64Codec.decode(value, urlSafe = true))
    private fun id(prefix:String)="${prefix}_${UUID.randomUUID().toString().replace("-","")}"
    private fun fail(message:String,errorId:String,transient:Boolean=false,cause:Throwable?=null):Nothing=throw MessageException(message,errorId,transient,cause)
    companion object { private const val MAX_TTL=7L*24*60*60*1000; private const val MAX_CONTENT=256*1024; private const val RETENTION_MS=7L*24*60*60*1000 }
}

private class MessageException(message:String,val errorId:String,val transient:Boolean=false,cause:Throwable?=null):RuntimeException(message,cause)
