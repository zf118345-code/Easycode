package com.easycode.player.extension

import android.app.Service
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import android.os.Process
import com.easycode.extension.api.AndroidExtensionContext
import com.easycode.extension.api.AndroidExtensionFunction
import com.easycode.player.util.JsonSupport
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import com.google.gson.JsonParser
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicBoolean

internal object ExtensionWorkerProtocol {
    const val HELLO = 1
    const val INVOKE = 2
    const val CANCEL = 3
    const val RESPONSE = 4
    const val MAX_JSON_CHARS = 512 * 1024
}

class AndroidExtensionWorkerService : Service() {
    private val executor = Executors.newSingleThreadExecutor { runnable ->
        Thread(runnable, "easycode-android-extension").apply { isDaemon = false }
    }
    @Volatile private var cancellation = AtomicBoolean(false)
    private val messenger = Messenger(Handler(Looper.getMainLooper()) { message ->
        when (message.what) {
            ExtensionWorkerProtocol.HELLO -> {
                reply(message, ok = true, workerPid = Process.myPid())
                true
            }
            ExtensionWorkerProtocol.CANCEL -> {
                cancellation.set(true)
                true
            }
            ExtensionWorkerProtocol.INVOKE -> {
                val request = message.data
                val target = message.replyTo
                val nextCancellation = AtomicBoolean(false)
                cancellation = nextCancellation
                executor.execute { invoke(target, request, nextCancellation) }
                true
            }
            else -> false
        }
    })

    override fun onBind(intent: Intent?): IBinder = messenger.binder

    override fun onDestroy() {
        cancellation.set(true)
        executor.shutdownNow()
        super.onDestroy()
    }

    private fun invoke(replyTo: Messenger?, request: Bundle, cancelled: AtomicBoolean) {
        val className = request.getString("class_name").orEmpty()
        val requestJson = request.getString("request_json").orEmpty()
        val events = JsonArray()
        try {
            if (className.isBlank() || requestJson.length > ExtensionWorkerProtocol.MAX_JSON_CHARS) {
                throw IllegalArgumentException("扩展请求或入口无效")
            }
            val parsedRequest = JsonParser.parseString(requestJson)
            if (!parsedRequest.isJsonObject || parsedRequest.asJsonObject.get("schema_version")?.asInt != 1) {
                throw IllegalArgumentException("扩展请求协议无效")
            }
            val implementation = Class.forName(className).getDeclaredConstructor().newInstance()
            if (implementation !is AndroidExtensionFunction) {
                throw IllegalArgumentException("扩展入口没有实现 EasyCode Android ABI")
            }
            val context = object : AndroidExtensionContext {
                override fun applicationContext() = this@AndroidExtensionWorkerService.applicationContext
                override fun runId(): String = request.getString("run_id").orEmpty()
                override fun packageId(): String = request.getString("package_id").orEmpty()
                override fun functionId(): String = request.getString("function_id").orEmpty()
                override fun isCancellationRequested(): Boolean = cancelled.get()
                override fun emit(level: String?, category: String?, message: String?) {
                    val normalizedLevel = level.orEmpty().takeIf { it in setOf("info", "warning", "error") } ?: "info"
                    val text = message.orEmpty().take(8_192)
                    events.add(JsonObject().apply {
                        addProperty("level", normalizedLevel)
                        addProperty("category", category.orEmpty().take(120).ifBlank { "extension" })
                        addProperty("message", text)
                    })
                }
            }
            val responseJson = implementation.invoke(context, requestJson)
            if (responseJson.length > ExtensionWorkerProtocol.MAX_JSON_CHARS) {
                throw IllegalArgumentException("扩展返回超过 512 KiB")
            }
            val value = JsonParser.parseString(responseJson)
            send(replyTo, Bundle().apply {
                putBoolean("ok", true)
                putString("value_json", value.toString())
                putString("events_json", events.toString())
                putInt("worker_pid", Process.myPid())
            })
        } catch (error: Throwable) {
            send(replyTo, Bundle().apply {
                putBoolean("ok", false)
                putString("error_id", "extension.execution_failed")
                putString("message", (error.message ?: error.javaClass.simpleName).take(4_096))
                putString("events_json", events.toString())
                putInt("worker_pid", Process.myPid())
            })
        }
    }

    private fun reply(message: Message, ok: Boolean, workerPid: Int) {
        send(message.replyTo, Bundle().apply {
            putBoolean("ok", ok)
            putInt("worker_pid", workerPid)
        })
    }

    private fun send(target: Messenger?, payload: Bundle) {
        if (target == null) return
        runCatching {
            target.send(Message.obtain(null, ExtensionWorkerProtocol.RESPONSE).apply { data = payload })
        }
    }
}
