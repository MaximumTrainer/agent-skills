package com.example.flow.core.port

import com.example.flow.core.domain.Flow
import java.util.Optional
import java.util.UUID

interface FlowRepository {
    fun findById(id: UUID): Optional<Flow>
    fun findByName(name: String): Optional<Flow>
    fun save(flow: Flow): Flow
}
