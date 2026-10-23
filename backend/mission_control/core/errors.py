"""Domain errors mapped to explicit HTTP responses by the API layer."""

from __future__ import annotations


class MissionControlError(Exception):
    status_code = 400
    code = "mission_control_error"

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class ValidationProblem(MissionControlError):
    status_code = 422
    code = "validation_error"


class NotFound(MissionControlError):
    status_code = 404
    code = "not_found"


class Conflict(MissionControlError):
    status_code = 409
    code = "conflict"


class CapabilityUnavailable(MissionControlError):
    status_code = 409
    code = "capability_unavailable"


class LaunchProblem(MissionControlError):
    status_code = 422
    code = "launch_failed"


class AdapterProblem(MissionControlError):
    status_code = 502
    code = "adapter_failed"
