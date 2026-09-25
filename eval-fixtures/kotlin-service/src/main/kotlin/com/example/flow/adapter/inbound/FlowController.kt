package com.example.flow.adapter.inbound

import com.example.flow.application.FlowService
import com.example.flow.core.domain.Flow
import org.springframework.web.bind.annotation.*
import java.util.UUID

@RestController
@RequestMapping("/flows")
class FlowController(private val service: FlowService) {

    @PostMapping("/{id}/activate")
    fun activate(@PathVariable id: UUID): Flow = service.activate(id)

    @PatchMapping("/{id}")
    fun rename(@PathVariable id: UUID, @RequestBody body: Map<String, String>): Flow =
        service.rename(id, body["name"]!!)
}
