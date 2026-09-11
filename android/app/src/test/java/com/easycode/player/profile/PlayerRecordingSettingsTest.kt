package com.easycode.player.profile

import com.google.gson.JsonObject
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull
import org.junit.Test

class PlayerRecordingSettingsTest {
    @Test
    fun defaultsAreDisabledAndBounded() {
        val value = normalizeRecordingSettings(null, 7)
        assertEquals(false, value.get("enabled").asBoolean)
        assertEquals("changed_frames", value.get("strategy").asString)
        assertNull(value.get("confirmed_profile_revision").takeUnless { it.isJsonNull })
    }

    @Test
    fun explicitConsentBindsRecordingToNewProfileRevision() {
        val value = normalizeRecordingSettings(JsonObject().apply {
            addProperty("enabled", true)
            addProperty("strategy", "all_frames")
            addProperty("target_fps", 5)
            addProperty("max_duration_ms", 10_000)
            addProperty("max_session_bytes", 10_485_760)
            addProperty("min_free_bytes", 67_108_864)
            addProperty("confirm_current_revision", true)
        }, profileRevision = 4, confirmed = true)

        assertEquals(true, value.get("enabled").asBoolean)
        assertEquals(4, value.get("confirmed_profile_revision").asInt)
        assertEquals(false, value.has("confirm_current_revision"))
    }

    @Test
    fun unrelatedProfileMutationKeepsOldConsentStale() {
        val value = normalizeRecordingSettings(JsonObject().apply {
            addProperty("enabled", true)
            addProperty("strategy", "diagnostic")
            addProperty("target_fps", 10)
            addProperty("max_duration_ms", 10_000)
            addProperty("max_session_bytes", 10_485_760)
            addProperty("min_free_bytes", 67_108_864)
            addProperty("confirmed_profile_revision", 3)
        }, profileRevision = 4)

        assertEquals(3, value.get("confirmed_profile_revision").asInt)
    }

    @Test
    fun enabledRecordingCannotBeSavedWithoutExplicitConsent() {
        val error = assertFailsWith<ProfileException> {
            normalizeRecordingSettings(JsonObject().apply {
                addProperty("enabled", true)
            }, profileRevision = 2, confirmed = false)
        }
        assertEquals("AND-PROFILE-015", error.code)
    }
}
