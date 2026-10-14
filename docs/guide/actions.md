# Actions

Nexigon Hub uses an **action-based API**: every operation -- querying devices,
setting properties, issuing tokens -- is represented by a dedicated Pydantic
model. You construct the action, pass it to `client.execute()`, and get back a
typed response.

## How it works

```python
from nexigon_hub_sdk.api_types import devices

# 1. Build the action with its parameters
action = devices.GetDeviceDetailsAction(device_id="d_...")

# 2. Execute it
output = client.execute(action)

# 3. Use the typed output
print(output.name)
print(output.is_connected)
```

Each action class documents the operation it performs and the fields it accepts.
The return type is statically known -- `execute(GetDeviceDetailsAction(...))` returns
`GetDeviceDetailsOutput`, not a generic dict.

## Action categories

Actions are organized by API domain:

| Module | Domain |
|--------|--------|
| `api_types.users` | User accounts, tokens, sessions, registration |
| `api_types.organizations` | Organizations, members, invitations |
| `api_types.projects` | Projects, deployment tokens, audit log |
| `api_types.devices` | Devices, certificates, connections, events, properties |
| `api_types.repositories` | Repositories, packages, versions, assets |
| `api_types.fleet` | Fleet-wide properties |
| `api_types.audit` | Global audit log |
| `api_types.jobs` | Background jobs |
| `api_types.instance` | Instance settings and statistics |
| `api_types.cluster` | Cluster node management |

## Naming conventions

Actions follow a consistent naming pattern:

- `Query*Action` -- list resources (returns a wrapper with a list field)
- `Get*DetailsAction` -- get a single resource by ID
- `Create*Action` -- create a new resource
- `Delete*Action` -- delete a resource
- `Set*Action` -- update a specific field on a resource

## Serialization

Action models use `camelCase` aliases for JSON serialization (matching the HTTP
API) while exposing `snake_case` attributes in Python:

```python
action = devices.GetDeviceDetailsAction(device_id="d_...")

# Python attribute
action.device_id  # "d_..."

# JSON sent to the API
action.model_dump_json(by_alias=True)  # '{"deviceId": "d_..."}'
```

You always work with `snake_case` in Python -- the SDK handles the conversion.

## Package Display Information

A package's `name` is its URL-safe path component. Its optional `presentation`
provides a human-readable display name, a CommonMark description, and a static
PNG image. Omitting a display name makes the Hub UI use the package name.

A repository package manager can create a package with `presentation` or update
it with `SetPackagePresentationAction`. Both accept `PackagePresentationUpdate`.
Omitted display name and description fields are cleared. Omitting `image`
preserves the existing PNG. Use `PackageImageUpdate_Remove()` to remove it.

```python
import base64
from pathlib import Path

from nexigon_hub_sdk.api_types import repositories

client.execute(
    repositories.SetPackagePresentationAction(
        package_id="pkg_...",
        presentation=repositories.PackagePresentationUpdate(
            display_name="Factory Controller",
            description="## Setup\n\nInstall the **signed** controller image.",
            image=repositories.PackageImageUpdate_Replace(
                image_png=base64.b64encode(Path("controller.png").read_bytes()).decode(),
            ),
        ),
    )
)
```

Image replacements contain base64-encoded PNG data without a data URL prefix.
The default limits are 1 MiB of PNG data and 1024 × 1024 pixels. Operators can
lower these limits; `GetPackageDetailsAction` returns the active `image_limits`.
Invalid, truncated, animated, or oversized PNGs reject the entire change.

Display names allow up to 128 characters and descriptions up to 65,536 characters.
The Hub renders CommonMark without raw HTML or embedded images. Package lists
include the display name; package details include the description and an optional
`presentation.image_url`, without image bytes.

### Fetch a Package Image

Resolve `image_url` against the Hub's origin and fetch it using the same
credentials as package details. The URL has this form:

```text
/api/v1/packages/{package_id}/image?v={content_hash}
```

The `v` parameter changes when the saved PNG changes so browsers refresh the
image after an edit. The endpoint always serves the current image and supports
GET and HEAD. A successful GET returns `image/png` and an `ETag`. Send that
value in `If-None-Match` to receive an empty `304 Not Modified` response when
the image is unchanged. Responses use `Cache-Control: private, no-cache`;
clients must revalidate cached images.

Access is checked on every request, including conditional requests, using the
same package view permission as `GetPackageDetailsAction`. Repository visibility
alone does not grant this permission. Missing or removed images return 404 for
authorized callers. Image URLs contain no credentials and do not grant access
by themselves.
