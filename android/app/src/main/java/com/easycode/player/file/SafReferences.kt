package com.easycode.player.file

import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.database.Cursor
import android.net.Uri
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import com.easycode.player.profile.ProfileException
import com.easycode.player.util.JsonSupport
import com.easycode.player.util.JsonSupport.array
import com.easycode.player.util.JsonSupport.string
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import java.net.URLDecoder
import java.nio.charset.StandardCharsets

object SafReferences {
    fun file(
        context: Context,
        uri: Uri,
        actionId: String,
        sourceType: String,
        resultFlags: Int,
    ): JsonObject {
        require(actionId in setOf("choose-file-read", "choose-file-save"))
        val requested = if (actionId == "choose-file-read") {
            Intent.FLAG_GRANT_READ_URI_PERMISSION
        } else {
            Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        }
        persist(context.contentResolver, uri, resultFlags, requested)
        val access = mutableSetOf(if (actionId == "choose-file-read") "read" else "write")
        val declared = sourceType.substringAfter('<', "").substringBeforeLast('>', "")
        if ("delete" in declared) access += "delete"
        return JsonObject().apply {
            addProperty("kind", "file_ref")
            addProperty("platform", "android")
            addProperty("source", "player_picker")
            addProperty("display_name", displayName(context.contentResolver, uri))
            addProperty("uri", uri.toString())
            addProperty("authorization_root_id", "android-document:${JsonSupport.sha256(uri.toString().toByteArray())}")
            add("access", JsonArray().also { values -> access.sorted().forEach(values::add) })
        }
    }

    fun directory(
        context: Context,
        uri: Uri,
        sourceType: String,
        resultFlags: Int,
    ): JsonObject {
        val requested = directoryIntentFlags(sourceType)
        persist(context.contentResolver, uri, resultFlags, requested)
        val declared = declaredDirectoryCapability(sourceType)
        val access = mutableSetOf<String>()
        if (declared.contains("read") || declared in setOf("list", "read_write")) access += "read"
        if (declared.contains("write") || declared in setOf("create", "move", "delete_empty", "read_write")) access += "write"
        if (declared.contains("list") || declared.contains("read") || declared == "read_write") access += "list"
        if (declared.contains("create") || declared.contains("write") || declared == "read_write") access += "create"
        if (declared.contains("move")) access += "move"
        if (declared.contains("delete_empty")) access += "delete_empty"
        // delete_tree is deliberately not granted by the picker.  It requires
        // a separate per-execution dangerous confirmation and provider proof.
        return JsonObject().apply {
            addProperty("kind", "directory_ref")
            addProperty("platform", "android")
            addProperty("source", "player_picker")
            addProperty("display_name", displayName(context.contentResolver, uri))
            addProperty("uri", uri.toString())
            addProperty("authorization_root_id", "android-tree:${JsonSupport.sha256(uri.toString().toByteArray())}")
            add("access", JsonArray().also { values -> access.sorted().forEach(values::add) })
        }
    }

    fun requiresDeleteTreeAuthorization(sourceType: String): Boolean =
        declaredDirectoryCapability(sourceType) == "delete_tree"

    fun directoryIntentFlags(sourceType: String): Int = when (declaredDirectoryCapability(sourceType)) {
        "read", "list" -> Intent.FLAG_GRANT_READ_URI_PERMISSION
        // Tree mutation needs write access, while conflict checks, recursive
        // preflight, and provider boundary proof also need read access.
        else -> Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION
    }

    /** Adds the separately disclosed dangerous capability to one selected root.
     *
     * The ordinary ACTION_OPEN_DOCUMENT_TREE result above never calls this
     * helper.  PlayerActivity invokes it only from the positive action of a
     * second, explicit disclosure dialog, and the runtime still requires a
     * new in-memory confirmation for every actual execution.
     */
    fun authorizeDeleteTree(reference: JsonObject, sourceType: String): JsonObject {
        if (!requiresDeleteTreeAuthorization(sourceType)) {
            throw ProfileException("AND-DIR-001", "字段契约没有声明递归删除危险能力")
        }
        if (
            reference.string("kind") != "directory_ref" ||
            reference.string("platform") != "android" ||
            reference.string("authorization_root_id").isBlank() ||
            reference.string("uri").isBlank()
        ) {
            throw ProfileException("AND-DIR-002", "递归删除危险授权必须绑定真实 Android SAF 根")
        }
        val approved = reference.deepCopy()
        val access = approved.array("access").mapTo(sortedSetOf()) { it.asString }
        access += "delete_tree"
        approved.add("access", JsonArray().also { output -> access.forEach(output::add) })
        return approved
    }

    fun isStillAuthorized(context: Context, reference: JsonObject): Boolean {
        val uri = runCatching { Uri.parse(reference.string("uri")) }.getOrNull() ?: return false
        val required = reference.array("access").map { it.asString }.toSet()
        val permission = context.contentResolver.persistedUriPermissions.firstOrNull { it.uri == uri }
            ?: return false
        if ("read" in required && !permission.isReadPermission) return false
        if (("write" in required || "create" in required) && !permission.isWritePermission) return false
        return runCatching {
            context.contentResolver.query(uri, arrayOf(DocumentsContract.Document.COLUMN_DOCUMENT_ID), null, null, null)
                ?.use(Cursor::moveToFirst) == true
        }.getOrDefault(false)
    }

    private fun persist(
        resolver: ContentResolver,
        uri: Uri,
        returnedFlags: Int,
        requested: Int,
    ) {
        if (uri.scheme != ContentResolver.SCHEME_CONTENT) {
            throw ProfileException("AND-FILE-001", "Android 文件引用必须来自 content:// 系统选择器")
        }
        val actual = returnedFlags and requested
        if (actual != requested) {
            throw ProfileException("AND-FILE-002", "系统选择器没有返回所需读写授权")
        }
        try {
            resolver.takePersistableUriPermission(uri, requested)
        } catch (error: SecurityException) {
            throw ProfileException("AND-FILE-003", "文档提供者不允许保存所需授权", error)
        }
    }

    private fun displayName(resolver: ContentResolver, uri: Uri): String {
        val providerName = runCatching {
            resolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                if (!cursor.moveToFirst()) null else cursor.getString(0)
            }
        }.getOrNull().orEmpty()
        return friendlyDisplayName(providerName.ifBlank { uri.lastPathSegment.orEmpty() })
    }

    /**
     * Some DocumentsUI providers expose a tree document id such as
     * `primary:Download/EasyCodeData` as DISPLAY_NAME.  That id is useful for
     * authorization, but is implementation detail in a Player form.  Keep the
     * full value in the URI/root identity and project only its final segment.
     */
    internal fun friendlyDisplayName(raw: String): String {
        val decoded = runCatching { URLDecoder.decode(raw, StandardCharsets.UTF_8.name()) }
            .getOrDefault(raw)
            .trim()
            .trimEnd('/')
        return decoded.substringAfterLast('/').substringAfterLast(':')
            .ifBlank { "已授权文档" }
    }

    private fun declaredDirectoryCapability(sourceType: String): String =
        sourceType.substringAfter('<', "read_write").substringBeforeLast('>', "read_write")
}
