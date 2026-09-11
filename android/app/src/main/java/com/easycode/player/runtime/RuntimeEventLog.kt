package com.easycode.player.runtime

import com.easycode.player.util.AtomicFiles
import com.easycode.player.util.JsonSupport
import com.google.gson.JsonObject
import java.io.File
import java.io.FileOutputStream

class RuntimeEventLog(root: File, private val runId: String) : AutoCloseable {
    private val lock = Any()
    private val file = File(root, "$runId.jsonl")
    private val stream: FileOutputStream

    init {
        file.parentFile?.mkdirs()
        stream = FileOutputStream(file, true)
    }

    val path: String get() = file.absolutePath

    fun append(event: RuntimeEvent) = synchronized(lock) {
        val record = JsonObject().apply {
            addProperty("schema_version", 1)
            addProperty("sequence", event.sequence)
            addProperty("timestamp", event.timestamp)
            addProperty("level", event.level)
            addProperty("category", event.category)
            addProperty("message", event.message)
            addProperty("run_id", event.runId)
            addProperty("function_id", event.functionId)
            addProperty("instruction_id", event.instructionId)
            if (event.errorId.isNotBlank()) addProperty("error_id", event.errorId)
        }
        stream.write(JsonSupport.canonicalBytes(record))
        stream.write('\n'.code)
        stream.flush()
    }

    override fun close() = synchronized(lock) {
        runCatching { stream.fd.sync() }
        stream.close()
    }
}
