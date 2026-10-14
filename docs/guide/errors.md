# Error Handling

The SDK raises two exception types depending on where the error originates.

## API errors

[`ActionApiError`][nexigon_hub_sdk.ActionApiError] is raised when the Nexigon
Hub API returns an error response (4xx or 5xx). It carries the structured error
body, HTTP status code, and an optional retry delay:

```python
from nexigon_hub_sdk import ActionApiError
from nexigon_hub_sdk.api_types import devices

try:
    client.execute(devices.GetDeviceDetailsAction(device_id="d_nonexistent"))
except ActionApiError as exc:
    print(exc.status_code)   # e.g. 404
    print(exc.error.kind)    # error kind identifier
    print(exc.error.message) # human-readable message
    if exc.retry_after_seconds is not None:
        print(f"Retry after {exc.retry_after_seconds} seconds")
```

The retry delay comes from the HTTP `Retry-After` header, with the structured
error body's `retryAfterSeconds` field as a fallback. Hub uses it for rate-limit
and temporary-capacity errors. The SDK exposes the metadata but does not retry
actions automatically.

## Command transport errors

[`CommandInvocationError`][nexigon_hub_sdk.CommandInvocationError] is raised when
a device command fails at the **transport or protocol level** -- for example, if
the WebSocket connection drops or the server sends a malformed frame.

This is distinct from a command that the device executes but reports as failed.
A failed command still returns normally via the `Done` frame with an error
status; `CommandInvocationError` means the response never arrived.

```python
from nexigon_hub_sdk import CommandInvocationError

try:
    output = client.invoke_device_command("d_...", "reboot")
except CommandInvocationError as exc:
    print(f"Transport failure: {exc}")
```

## Summary

| Exception                                                          | When                                               |
| ------------------------------------------------------------------ | -------------------------------------------------- |
| [`ActionApiError`][nexigon_hub_sdk.ActionApiError]                 | API returned an error response                     |
| [`CommandInvocationError`][nexigon_hub_sdk.CommandInvocationError] | WebSocket/protocol failure during a device command |
