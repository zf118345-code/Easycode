package com.easycode.player.schedule

import com.google.gson.JsonObject
import java.time.Instant
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertNotEquals
import org.junit.Test

class AndroidScheduleTriggerTest {
    @Test
    fun remoteDispatchIdentityIsStableAndContentSensitive() {
        val original = JsonObject().apply {
            addProperty("dispatch_id", "dispatch_android_real_002")
            addProperty("entry_id", "entry_android_real_002")
            addProperty("schedule_revision", 1)
        }
        val reordered = JsonObject().apply {
            addProperty("schedule_revision", 1)
            addProperty("entry_id", "entry_android_real_002")
            addProperty("dispatch_id", "dispatch_android_real_002")
        }
        val changed = reordered.deepCopy().apply {
            addProperty("entry_id", "entry_android_changed")
        }

        assertEquals(remoteDispatchFingerprint(original), remoteDispatchFingerprint(reordered))
        assertNotEquals(remoteDispatchFingerprint(original), remoteDispatchFingerprint(changed))
        assertEquals(
            "run_0e009abdf943fb75b86d7eb3eaf6b594",
            remoteDispatchRunId("dispatch_android_real_002"),
        )
    }

    @Test
    fun intervalUsesAnchorAndDoesNotDriftWithTaskDuration() {
        val trigger = JsonObject().apply {
            addProperty("kind", "interval")
            addProperty("anchor_time", "2026-09-03T00:00:00Z")
            addProperty("interval_ms", 600_000)
        }
        assertEquals(
            Instant.parse("2026-09-03T00:20:00Z"),
            nextScheduleTrigger(trigger, Instant.parse("2026-09-03T00:17:21Z")),
        )
    }

    @Test
    fun oneTimeDoesNotRepeatAfterItsOccurrence() {
        val trigger = JsonObject().apply { addProperty("kind", "one_time"); addProperty("at", "2026-09-03T01:00:00Z") }
        assertEquals(Instant.parse("2026-09-03T01:00:00Z"), nextScheduleTrigger(trigger, Instant.parse("2026-09-03T00:59:00Z")))
        assertNull(nextScheduleTrigger(trigger, Instant.parse("2026-09-03T01:00:00Z")))
    }

    @Test
    fun dailySpringGapMovesToFirstValidLocalTime() {
        val trigger = JsonObject().apply {
            addProperty("kind", "daily")
            addProperty("local_time", "02:30")
            addProperty("timezone_id", "America/New_York")
        }
        assertEquals(
            Instant.parse("2026-03-08T07:00:00Z"),
            nextScheduleTrigger(trigger, Instant.parse("2026-03-08T05:00:00Z")),
        )
    }
}
