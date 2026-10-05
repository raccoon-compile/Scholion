"""Private path-bearing bridge for native update activation.

Unlike the public update bridge, this adapter is never exposed as a caller-selected
Tauri request surface. Rust invokes one fixed method after explicit user intent and
consumes the path-bearing ticket without forwarding it to the WebView.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from scholion.app.app_container import AppContainer
from scholion.app.update_composition import build_update_channel_service
from scholion.desktop.host_protocol import (
    failure_response,
    run_stdio_bridge,
    success_response,
)
from scholion.update_channel.service import UpdateChannelError, UpdateChannelService


class _ActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_version: Literal[1]
    request_id: str = Field(min_length=1, max_length=128)
    method: Literal["updates.native_activation_ticket"]
    params: dict[str, object] = Field(default_factory=dict)


class _NoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _service() -> UpdateChannelService:
    return build_update_channel_service(AppContainer())


def handle_request(
    payload: object,
    update_service: UpdateChannelService | None = None,
) -> dict[str, object]:
    try:
        request = _ActivationRequest.model_validate(payload)
        _NoParams.model_validate(request.params)
    except ValidationError:
        request_id = (
            payload.get("request_id", "unknown")
            if isinstance(payload, dict)
            else "unknown"
        )
        return failure_response(
            str(request_id)[:128],
            code="invalid_request",
            message="The native update activation request was invalid",
        )

    service = update_service or _service()
    try:
        result = service.native_activation_ticket()
    except UpdateChannelError:
        return failure_response(
            request.request_id,
            code="update_activation_not_authorized",
            message="Scholion could not authorize the staged update for installation",
        )
    return success_response(request.request_id, result)


def main() -> int:
    return run_stdio_bridge(
        handle_request,
        oversized_message="The native update activation request exceeded the safe size limit",
        invalid_json_message="The native update activation request was not valid JSON",
    )


if __name__ == "__main__":
    raise SystemExit(main())
