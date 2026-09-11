package com.easycode.player.profile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class PlayerControlDestinationTest {
    @Test
    fun `host file picker may run without operation target`() {
        val destination = PlayerControlDestination(
            productId = "project_1",
            releaseId = "release_1",
            profileId = "profile_1",
            controlId = "input_file",
            actionId = "choose-file-read",
            profileRevision = 1,
            targetId = "",
        )

        assertEquals("", destination.targetId)
        assertEquals("choose-file-read", destination.actionId)
    }

    @Test
    fun `screen capture still requires a real android target`() {
        assertThrows(IllegalArgumentException::class.java) {
            PlayerControlDestination(
                productId = "project_1",
                releaseId = "release_1",
                profileId = "profile_1",
                controlId = "point",
                actionId = "pick-point",
                profileRevision = 1,
                targetId = "",
            )
        }
    }
}
