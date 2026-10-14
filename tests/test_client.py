import asyncio
import json

import httpx
import pytest

from nexigon_hub_sdk import ActionApiError, AsyncClient, Client
from nexigon_hub_sdk._actions import _ACTION_REGISTRY
from nexigon_hub_sdk.api_types import (
    audit,
    devices,
    pagination,
    projects,
    users,
)


def test_action_request_encoding() -> None:
    """Actions serialize to camelCase JSON matching the server's expectations."""
    action = users.GetUserDetailsAction(
        user_id=users.UserId("u_9JTb4Drw5fbVWpoqM8fwvg")
    )
    payload = json.loads(action.model_dump_json(by_alias=True))
    assert payload == {"userId": "u_9JTb4Drw5fbVWpoqM8fwvg"}


def test_property_schema_round_trip() -> None:
    """Schema documents use the wire alias without shadowing BaseModel.schema."""
    for definition in [
        False,
        {"type": "object", "properties": {"enabled": {"type": "boolean"}}},
    ]:
        action = projects.SetPropertySchemaAction(
            project_id=projects.ProjectId("p_example"),
            name="com.example.config",
            json_schema=definition,
        )
        assert (
            _ACTION_REGISTRY[projects.SetPropertySchemaAction][0]
            == "projects_SetPropertySchema"
        )
        payload = json.loads(action.model_dump_json(by_alias=True))
        assert payload == {
            "projectId": "p_example",
            "name": "com.example.config",
            "schema": definition,
        }
        result = projects.PropertySchema.model_validate(
            {"name": action.name, "schema": definition, "builtin": False}
        )
        assert result.json_schema == definition
        assert json.loads(result.model_dump_json(by_alias=True))["schema"] == definition


def test_action_response_decoding() -> None:
    """Output types deserialize from camelCase JSON."""
    _, adapter = _ACTION_REGISTRY[users.GetUserDetailsAction]
    output = adapter.validate_json(
        json.dumps(
            {
                "userId": "u_9JTb4Drw5fbVWpoqM8fwvg",
                "email": "alice@example.com",
                "displayName": "Alice",
                "isAdmin": False,
            }
        )
    )
    assert isinstance(output, users.GetUserDetailsOutput)
    assert output.user_id == "u_9JTb4Drw5fbVWpoqM8fwvg"
    assert output.display_name == "Alice"


def test_execute_success() -> None:
    """Client.execute round-trips a successful action call."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200,
            json={
                "userId": "u_9JTb4Drw5fbVWpoqM8fwvg",
                "email": "bob@example.com",
                "displayName": None,
                "isAdmin": True,
            },
        )
    )
    client = Client.__new__(Client)
    client._http = httpx.Client(transport=transport, base_url="http://test/api/v1/")

    result = client.execute(
        users.GetUserDetailsAction(user_id=users.UserId("u_9JTb4Drw5fbVWpoqM8fwvg"))
    )
    assert isinstance(result, users.GetUserDetailsOutput)
    assert result.email == "bob@example.com"
    assert result.is_admin is True


def test_audit_cursor_round_trip() -> None:
    """The typed client carries a response cursor unchanged into the next request."""
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "events": [],
                "page": {"nextCursor": "opaque-cursor"} if len(requests) == 1 else {},
            },
        )

    client = Client.__new__(Client)
    client._http = httpx.Client(
        transport=httpx.MockTransport(respond), base_url="http://test/api/v1/"
    )
    try:
        first = client.execute(
            audit.QueryAuditLogEventsAction(page=pagination.PageRequest(limit=2))
        )
        assert first.page is not None
        second = client.execute(
            audit.QueryAuditLogEventsAction(
                page=pagination.PageRequest(limit=2, cursor=first.page.next_cursor)
            )
        )
        assert requests[1]["page"] == {"limit": 2, "cursor": "opaque-cursor"}
        assert second.page is not None
        assert second.page.next_cursor is None
    finally:
        client.close()


def test_execute_error() -> None:
    """Client.execute raises ActionApiError on error responses."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            403,
            json={"kind": "Forbidden", "message": "Not allowed"},
        )
    )
    client = Client.__new__(Client)
    client._http = httpx.Client(transport=transport, base_url="http://test/api/v1/")

    with pytest.raises(ActionApiError) as exc_info:
        client.execute(users.QueryUsersAction())

    assert exc_info.value.status_code == 403
    assert "Forbidden" in str(exc_info.value)


def test_execute_error_exposes_retry_metadata() -> None:
    """Retryable action errors expose the server's Retry-After delay."""
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            503,
            headers={"Retry-After": "3"},
            json={
                "kind": "Unavailable",
                "message": "Service temporarily unavailable",
                "retryAfterSeconds": 2,
            },
        )
    )
    client = Client.__new__(Client)
    client._http = httpx.Client(transport=transport, base_url="http://test/api/v1/")

    with pytest.raises(ActionApiError) as exc_info:
        client.execute(users.QueryUsersAction())

    assert exc_info.value.status_code == 503
    assert exc_info.value.retry_after_seconds == 3
    assert exc_info.value.error.retry_after_seconds == 2


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
def test_plaintext_requires_explicit_opt_in(
    client_type: type[Client] | type[AsyncClient],
) -> None:
    with pytest.raises(ValueError, match="plaintext HTTP"):
        client_type("http://hub.example", token="sentinel-token")


@pytest.mark.parametrize("client_type", [Client, AsyncClient])
def test_explicit_plaintext_opt_in(
    client_type: type[Client] | type[AsyncClient],
) -> None:
    client = client_type(
        "http://127.0.0.1:8080/",
        token="sentinel-token",
        dangerous_allow_plaintext=True,
    )
    assert client._base_url == "http://127.0.0.1:8080"
    if isinstance(client, Client):
        client.close()
    else:
        asyncio.run(client.aclose())


@pytest.mark.parametrize("base_url", ["ftp://hub.example", "hub.example", "/relative"])
def test_unsupported_base_url_is_rejected(base_url: str) -> None:
    with pytest.raises(ValueError, match="HTTPS URL|use HTTPS"):
        Client(base_url, token="sentinel-token")


@pytest.mark.asyncio
@pytest.mark.parametrize("asynchronous", [False, True])
async def test_execute_omits_absent_fields_and_preserves_json_null(
    asynchronous: bool,
) -> None:
    """Both HTTP clients omit optional None fields while preserving required JSON null."""
    requests: list[dict[str, object]] = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"result": "Set"})

    action = devices.SetDevicePropertyAction(
        device_id=devices.DeviceId("d_example"),
        name="com.example.value",
        value=None,
        protected=None,
    )
    transport = httpx.MockTransport(respond)
    if asynchronous:
        async_client = AsyncClient.__new__(AsyncClient)
        async_client._http = httpx.AsyncClient(
            transport=transport, base_url="http://test/api/v1/"
        )
        try:
            await async_client.execute(action)
        finally:
            await async_client.aclose()
    else:
        client = Client.__new__(Client)
        client._http = httpx.Client(transport=transport, base_url="http://test/api/v1/")
        try:
            client.execute(action)
        finally:
            client.close()
    assert requests == [
        {"deviceId": "d_example", "name": "com.example.value", "value": None}
    ]
