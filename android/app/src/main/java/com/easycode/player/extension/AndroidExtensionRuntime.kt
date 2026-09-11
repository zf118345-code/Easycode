package com.easycode.player.extension

import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.ServiceConnection
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.Message
import android.os.Messenger
import android.os.Process
import com.easycode.player.bundle.VerifiedBundle
import com.easycode.player.runtime.RuntimeControl
import com.easycode.player.runtime.RuntimeFailure
import com.easycode.player.util.JsonSupport
import com.google.gson.JsonArray
import com.google.gson.JsonParser
import java.util.UUID
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean

class AndroidExtensionRuntime(
    private val context: Context,
    private val bundle: VerifiedBundle,
    private val runId: String,
    private val control: RuntimeControl,
    private val onEvent: (level: String, category: String, message: String) -> Unit,
) : AutoCloseable {
    fun execute(
        instructionId: String,
        functionId: String,
        arguments: Map<String, Any?>,
        timeoutMs: Long,
    ): Any? {
        val entry = bundle.extensionRegistry.entries[functionId]
            ?: throw RuntimeFailure("extension.not_available", "Android 扩展函数没有进入 APK：$functionId")
        if (timeoutMs !in 50L..600_000L) {
            throw RuntimeFailure("extension.contract_invalid", "扩展超时必须位于 50..600000 毫秒")
        }
        val requestId = UUID.randomUUID().toString()
        val requestJson = JsonSupport.fromAny(linkedMapOf(
            "schema_version" to 1,
            "request_id" to requestId,
            "run_id" to runId,
            "release_id" to bundle.releaseId,
            "package_id" to entry.packageId,
            "function_id" to functionId,
            "instruction_id" to instructionId,
            "arguments" to arguments,
        )).toString()
        if (requestJson.length > ExtensionWorkerProtocol.MAX_JSON_CHARS) {
            throw RuntimeFailure("extension.arguments_invalid", "扩展参数超过 512 KiB")
        }

        val replies = HandlerThread("easycode-extension-reply-$requestId").apply { start() }
        val hello = CountDownLatch(1)
        val completed = CountDownLatch(1)
        var remote: Messenger? = null
        var workerPid = 0
        var response: Bundle? = null
        val disconnected = AtomicBoolean(false)
        var invocationFinished = false
        val reply = Messenger(Handler(replies.looper) { message ->
            if (message.what != ExtensionWorkerProtocol.RESPONSE) return@Handler false
            val payload = message.data
            val pid = payload.getInt("worker_pid", 0)
            if (workerPid == 0 && pid > 0) {
                workerPid = pid
                hello.countDown()
            } else {
                response = payload
                completed.countDown()
            }
            true
        })
        val connection = object : ServiceConnection {
            override fun onServiceConnected(name: ComponentName?, service: IBinder?) {
                remote = Messenger(service)
                remote?.send(Message.obtain(null, ExtensionWorkerProtocol.HELLO).apply { replyTo = reply })
            }

            override fun onServiceDisconnected(name: ComponentName?) {
                disconnected.set(true)
                hello.countDown()
                completed.countDown()
            }

            override fun onBindingDied(name: ComponentName?) = onServiceDisconnected(name)
            override fun onNullBinding(name: ComponentName?) = onServiceDisconnected(name)
        }
        val bound = context.bindService(
            Intent(context, AndroidExtensionWorkerService::class.java),
            connection,
            Context.BIND_AUTO_CREATE,
        )
        if (!bound) {
            replies.quitSafely()
            throw RuntimeFailure("extension.worker_unavailable", "Android 扩展 Worker 无法启动", transient = true)
        }
        try {
            await(hello, 5_000L)
            if (disconnected.get() || workerPid <= 0 || remote == null) {
                throw RuntimeFailure("extension.worker_crashed", "Android 扩展 Worker 在执行前退出", transient = true)
            }
            try {
                remote!!.send(Message.obtain(null, ExtensionWorkerProtocol.INVOKE).apply {
                    replyTo = reply
                    data = Bundle().apply {
                        putString("class_name", entry.className)
                        putString("request_json", requestJson)
                        putString("run_id", runId)
                        putString("package_id", entry.packageId)
                        putString("function_id", functionId)
                    }
                })
            } catch (error: Throwable) {
                throw RuntimeFailure("extension.worker_crashed", "Android 扩展 Worker 无法接收请求", transient = true)
            }
            val deadline = System.nanoTime() + timeoutMs * 1_000_000L
            while (!completed.await(50L, TimeUnit.MILLISECONDS)) {
                control.checkpoint()
                if (System.nanoTime() >= deadline) {
                    remote?.send(Message.obtain(null, ExtensionWorkerProtocol.CANCEL))
                    if (workerPid > 0) Process.killProcess(workerPid)
                    throw RuntimeFailure("extension.timeout", "Android 扩展执行超时", transient = true)
                }
            }
            if (disconnected.get() && response == null) {
                throw RuntimeFailure("extension.worker_crashed", "Android 扩展 Worker 意外退出", transient = true)
            }
            val payload = response ?: throw RuntimeFailure("extension.worker_protocol", "Android 扩展 Worker 没有返回结果")
            invocationFinished = true
            emitEvents(payload.getString("events_json").orEmpty())
            if (!payload.getBoolean("ok")) {
                throw RuntimeFailure(
                    payload.getString("error_id").orEmpty().ifBlank { "extension.execution_failed" },
                    payload.getString("message").orEmpty().ifBlank { "Android 扩展执行失败" },
                )
            }
            val valueJson = payload.getString("value_json")
                ?: throw RuntimeFailure("extension.worker_protocol", "Android 扩展返回缺少 value_json")
            return JsonSupport.toAny(JsonParser.parseString(valueJson))
        } finally {
            if (!invocationFinished) {
                runCatching { remote?.send(Message.obtain(null, ExtensionWorkerProtocol.CANCEL)) }
                if (workerPid > 0) runCatching { Process.killProcess(workerPid) }
            }
            runCatching { context.unbindService(connection) }
            replies.quitSafely()
        }
    }

    private fun await(latch: CountDownLatch, timeoutMs: Long) {
        val deadline = System.nanoTime() + timeoutMs * 1_000_000L
        while (!latch.await(50L, TimeUnit.MILLISECONDS)) {
            control.checkpoint()
            if (System.nanoTime() >= deadline) return
        }
    }

    private fun emitEvents(raw: String) {
        val events = runCatching { JsonParser.parseString(raw).asJsonArray }.getOrElse { JsonArray() }
        for (item in events) {
            if (!item.isJsonObject) continue
            val event = item.asJsonObject
            onEvent(
                event.get("level")?.asString ?: "info",
                event.get("category")?.asString ?: "extension",
                event.get("message")?.asString ?: "",
            )
        }
    }

    override fun close() = Unit
}
