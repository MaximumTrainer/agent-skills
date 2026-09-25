package com.example.flow

import com.example.flow.core.domain.Flow
import com.example.flow.core.domain.Staleness
import org.junit.jupiter.api.Test
import java.time.Instant
import java.util.UUID

class StalenessTest {

    @Test
    fun testBand() {
        val flow = Flow(UUID.randomUUID(), "n", "DRAFT", Instant.now())
        val band = Staleness.band(flow)
        assert(band != null)
    }
}
