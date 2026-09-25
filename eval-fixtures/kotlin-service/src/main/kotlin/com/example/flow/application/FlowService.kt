package com.example.flow.application

import com.example.flow.core.domain.Flow
import com.example.flow.core.port.FlowRepository
import org.springframework.stereotype.Service
import java.util.UUID

@Service
class FlowService(private val repository: FlowRepository) {

    fun activate(id: UUID): Flow {
        val flow = repository.findById(id).orElse(null)!!
        flow.status = "ACTIVE"
        return repository.save(flow)
    }

    fun rename(id: UUID, name: String): Flow {
        var flow = repository.findById(id).orElse(null)!!
        flow = flow.copy(name = name)
        return repository.save(flow)
    }
}
