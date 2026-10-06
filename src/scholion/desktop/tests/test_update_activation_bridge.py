from typing import Any, cast

from scholion.desktop.update_activation_bridge import handle_request


class _Service:
    def __init__(self) -> None:
        self.calls = 0
        self.fail = False

    def native_activation_ticket(self) -> dict[str, object]:
        self.calls += 1
        if self.fail:
            from scholion.update_channel.service import UpdateChannelError

            raise UpdateChannelError("private activation detail")
        return {
            "schema_version": 1,
            "platform": "windows-x86_64",
            "version": "0.2.0",
            "sequence": 2,
            "size_bytes": 42,
            "sha256": "a" * 64,
            "staged_path": "C:/private/cache/update.exe",
        }


def _request(
    method: str = "updates.native_activation_ticket",
    *,
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "protocol_version": 1,
        "request_id": "native-update-activation",
        "method": method,
        "params": params or {},
    }


def test_private_activation_bridge_exposes_only_fixed_no_param_ticket() -> None:
    service = _Service()

    response = handle_request(_request(), cast(Any, service))

    assert response["ok"] is True
    assert service.calls == 1
    assert response["result"]["staged_path"] == "C:/private/cache/update.exe"


def test_private_activation_bridge_rejects_caller_paths_and_other_methods() -> None:
    service = _Service()

    with_path = handle_request(
        _request(params={"path": "C:/evil.exe"}),
        cast(Any, service),
    )
    public_method = handle_request(
        _request(method="updates.prepare_activation"),
        cast(Any, service),
    )

    assert with_path["ok"] is False
    assert public_method["ok"] is False
    assert service.calls == 0


def test_private_activation_failure_is_bounded() -> None:
    service = _Service()
    service.fail = True

    response = handle_request(_request(), cast(Any, service))

    assert response["ok"] is False
    assert response["error"] == {
        "code": "update_activation_not_authorized",
        "message": "Scholion could not authorize the staged update for installation",
    }
    assert "private activation detail" not in str(response)
