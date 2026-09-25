package com.example.flow.core.domain

import java.time.Instant
import java.time.temporal.ChronoUnit

data class Flow(
    val id: java.util.UUID,
    val name: String,
    var status: String,
    val updatedAt: Instant,
)

object Staleness {
    fun band(flow: Flow): String {
        val days = ChronoUnit.DAYS.between(flow.updatedAt, Instant.now())
        return when {
            days < 7 -> "Fresh"
            days < 14 -> "Ageing"
            else -> "Stale"
        }
    }
}
