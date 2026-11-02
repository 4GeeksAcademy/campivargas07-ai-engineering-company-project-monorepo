"""Regression coverage for the real MCP credential branch."""
import os
from unittest.mock import AsyncMock, Mock
import pytest
from app.domains.agent import mcp_client


def successful_result():
    return mcp_client.IncidentToolResult(status=mcp_client.IncidentToolStatus.SUCCESS, incidents=[], message='Consulta completada.')


def test_injected_provider_is_used(monkeypatch):
    provider = Mock()
    provider.get.return_value = 'test-access-token'
    resolver = Mock(side_effect=AssertionError('Must use injected provider'))
    invoke = AsyncMock(return_value=successful_result())
    monkeypatch.setattr(mcp_client, '_resolve_token_provider', resolver)
    monkeypatch.setattr(mcp_client, '_invoke_mcp_async', invoke)
    query = mcp_client.IncidentToolInput(status='open')
    result = mcp_client.query_incidents_via_mcp(query, server_url='https://mcp.example', token_provider=provider)
    assert result.status == mcp_client.IncidentToolStatus.SUCCESS
    provider.get.assert_called_once_with()
    resolver.assert_not_called()
    invoke.assert_awaited_once_with(query, server_url='https://mcp.example', token='test-access-token')


def test_environment_credentials_fetch_token(monkeypatch):
    env = {'AGENT_MCP_SERVER_URL': 'https://mcp.example', 'AGENT_MCP_TOKEN_URL': 'https://issuer.example/oauth/token', 'AGENT_MCP_CLIENT_ID': 'test-client', 'AGENT_MCP_CLIENT_SECRET': 'test-secret', 'AGENT_MCP_AUDIENCE': 'https://mcp.example/mcp', 'AGENT_MCP_SCOPES': 'incidents:read'}
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    post = Mock(return_value=mcp_client.httpx.Response(200, json={'access_token': 'test-access-token', 'expires_in': 3600}))
    invoke = AsyncMock(return_value=successful_result())
    monkeypatch.setattr(mcp_client.httpx, 'post', post)
    monkeypatch.setattr(mcp_client, '_invoke_mcp_async', invoke)
    query = mcp_client.IncidentToolInput(status='open')
    assert mcp_client.query_incidents_via_mcp(query).status == mcp_client.IncidentToolStatus.SUCCESS
    assert post.call_args.args == (env['AGENT_MCP_TOKEN_URL'],)
    assert post.call_args.kwargs['data'] == {'grant_type': 'client_credentials', 'client_id': 'test-client', 'client_secret': 'test-secret', 'scope': 'incidents:read', 'audience': 'https://mcp.example/mcp'}
    assert post.call_args.kwargs['follow_redirects'] is False
    invoke.assert_awaited_once_with(query, server_url='https://mcp.example', token='test-access-token')


def test_missing_credentials_fail_before_mcp(monkeypatch):
    for key in ('AGENT_MCP_TOKEN_URL', 'AGENT_MCP_CLIENT_ID', 'AGENT_MCP_CLIENT_SECRET', 'MCP_TOKEN_URL', 'MCP_CLIENT_ID', 'MCP_CLIENT_SECRET'):
        monkeypatch.delenv(key, raising=False)
    invoke = AsyncMock()
    monkeypatch.setattr(mcp_client, '_invoke_mcp_async', invoke)
    with pytest.raises(mcp_client.ConfigurationError):
        mcp_client.query_incidents_via_mcp(mcp_client.IncidentToolInput(), server_url='https://mcp.example')
    invoke.assert_not_awaited()
