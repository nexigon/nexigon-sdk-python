# Quick Start

## Creating a client

Both [`Client`][nexigon_hub_sdk.Client] and
[`AsyncClient`][nexigon_hub_sdk.AsyncClient] accept a base URL and an API token.
They work as context managers that close the underlying HTTP connection on exit.

=== "Sync"

    ```python
    from nexigon_hub_sdk import Client

    with Client("https://hub.example.com", token="your-api-token") as client:
        ...
    ```

=== "Async"

    ```python
    from nexigon_hub_sdk import AsyncClient

    async with AsyncClient("https://hub.example.com", token="your-api-token") as client:
        ...
    ```

## Executing actions

All API operations are represented as **action** objects. Import the action
class, construct it with the required parameters, and pass it to
`client.execute()`:

```python
from nexigon_hub_sdk.api_types import devices

output = client.execute(devices.GetDeviceDetailsAction(device_id="d_..."))
print(output.name)
print(output.is_connected)
```

Every `execute()` call is fully typed -- your IDE knows the exact return type
based on the action you pass in.

## Listing resources

Many actions follow a query/list pattern and return a wrapper with a list field.
Device listings return one page at a time, by default the 100 devices most
recently first seen. To list every device, pass `output.page.next_cursor` back
as `pagination.PageRequest(cursor=...)` until it is `None`:

```python
from nexigon_hub_sdk.api_types import pagination, projects

cursor = None
while True:
    output = client.execute(
        projects.QueryProjectDevicesAction(
            project_id="p_...", page=pagination.PageRequest(cursor=cursor)
        )
    )
    for device in output.devices:
        print(f"{device.device_id}: connected={device.is_connected}")
    cursor = output.page.next_cursor
    if cursor is None:
        break
```

Device events and audit logs paginate the same way once you pass
`page=pagination.PageRequest()`. Without it, they return their unpaginated
result and `output.page` is `None`. See
[Pagination](https://docs.nexigon.dev/reference/actions-api#pagination) for
page sizes, ordering, and consistency.

## Working with device properties

```python
from nexigon_hub_sdk.api_types import devices

# Set a property on a device
client.execute(devices.SetDevicePropertyAction(
    device_id="d_...",
    key="firmware-version",
    value="2.1.0",
))

# Read it back
output = client.execute(devices.GetDevicePropertyAction(
    device_id="d_...",
    key="firmware-version",
))
print(output.value)
```

## Issuing remote access URLs

Generate a short-lived HTTP proxy token for direct access to a connected device:

```python
from nexigon_hub_sdk.api_types import devices

output = client.execute(devices.IssueDeviceHttpProxyTokenAction(
    device_id="d_...",
))
print(output.token)
```

## Async usage

[`AsyncClient`][nexigon_hub_sdk.AsyncClient] has the same API surface -- just
`await` the calls:

```python
from nexigon_hub_sdk import AsyncClient
from nexigon_hub_sdk.api_types import projects

async with AsyncClient("https://hub.example.com", token="your-api-token") as client:
    output = await client.execute(
        projects.QueryProjectDevicesAction(project_id="p_...")
    )
    for device in output.devices:
        print(f"{device.device_id}: connected={device.is_connected}")
```

Both clients require HTTPS by default. For an explicitly trusted local development
network only, HTTP can be enabled with `dangerous_allow_plaintext=True`; this option
must not be used for deployed Hub credentials.
