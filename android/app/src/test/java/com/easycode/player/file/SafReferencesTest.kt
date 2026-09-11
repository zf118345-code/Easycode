package com.easycode.player.file

import android.content.Intent
import com.easycode.player.profile.ProfileException
import com.google.gson.JsonArray
import com.google.gson.JsonObject
import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class SafReferencesTest {
    @Test
    fun providerDocumentIdsAreProjectedAsReadableNames() {
        assertEquals("EasyCodeData", SafReferences.friendlyDisplayName("primary:Download/EasyCodeData"))
        assertEquals("tasks.json", SafReferences.friendlyDisplayName("tasks.json"))
        assertEquals("已授权文档", SafReferences.friendlyDisplayName(""))
    }

    @Test
    fun directoryPickerRequestsOnlyTheSystemModesNeededByTheDeclaredCapability() {
        assertEquals(
            Intent.FLAG_GRANT_READ_URI_PERMISSION,
            SafReferences.directoryIntentFlags("directory_ref<list>"),
        )
        assertEquals(
            Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            SafReferences.directoryIntentFlags("directory_ref<delete_tree>"),
        )
    }

    @Test
    fun ordinaryReferenceNeedsSeparateDeclaredAuthorizationBeforeDeleteTreeAccess() {
        val ordinary = reference()

        assertEquals(emptyList(), ordinary.getAsJsonArray("access").map { it.asString })
        assertFailsWith<ProfileException> {
            SafReferences.authorizeDeleteTree(ordinary, "directory_ref<read>")
        }

        val approved = SafReferences.authorizeDeleteTree(
            ordinary,
            "directory_ref<delete_tree>",
        )

        assertEquals(emptyList(), ordinary.getAsJsonArray("access").map { it.asString })
        assertEquals(listOf("delete_tree"), approved.getAsJsonArray("access").map { it.asString })
        assertEquals("root-a", approved.get("authorization_root_id").asString)
    }

    private fun reference(): JsonObject = JsonObject().apply {
        addProperty("kind", "directory_ref")
        addProperty("platform", "android")
        addProperty("source", "player_picker")
        addProperty("uri", "content://provider/tree/root")
        addProperty("authorization_root_id", "root-a")
        add("access", JsonArray())
    }
}
