import pytest
from app.domains.knowledge import router as knowledge
from data.process.config import ConfigurationError, ProviderError, StoreError


def test_auth_required(client, monkeypatch):
    monkeypatch.setattr(knowledge, 'query', lambda _: pytest.fail('No anonymous generation'))
    assert client.post('/knowledge/query', json={'question':'puntos'}).status_code in (401,403)


def test_invalid_token_cannot_generate(client, monkeypatch):
    monkeypatch.setattr(knowledge, 'query', lambda _: pytest.fail('No unauthenticated generation'))
    response = client.post('/knowledge/query', headers={'Authorization': 'Bearer invalid-token'},
                           json={'question': 'puntos'})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'


def test_inactive_user_cannot_generate(client, create_test_user, monkeypatch):
    from app.domains.auth.service import create_access_token
    user = create_test_user(is_active=False)
    token = create_access_token(data={'sub': str(user.doc_id), 'role': user['role']})
    monkeypatch.setattr(knowledge, 'query', lambda _: pytest.fail('No inactive user generation'))
    response = client.post('/knowledge/query', headers={'Authorization': f'Bearer {token}'},
                           json={'question': 'puntos'})
    assert response.status_code == 403


@pytest.mark.parametrize('body', [{}, {'question':''}, {'question':'  '}, {'question':'x'*2001}, {'question':3}, {'question':'q','k':3}])
def test_validation(client, auth_headers, body):
    assert client.post('/knowledge/query', headers=auth_headers, json=body).status_code == 422


def test_returns_only_model_answer(client, auth_headers, monkeypatch):
    seen = []
    monkeypatch.setattr(knowledge, 'query', lambda q: seen.append(q) or 'Respuesta generada')
    response = client.post('/knowledge/query', headers=auth_headers, json={'question':' puntos '})
    assert response.status_code == 200 and response.json() == {'answer':'Respuesta generada'}
    assert seen == ['puntos']


@pytest.mark.parametrize('error,status', [(ConfigurationError,503),(ProviderError,502),(StoreError,503)])
def test_safe_error(client, auth_headers, monkeypatch, error, status):
    def fail(_): raise error('secret token vector and provider URL')
    monkeypatch.setattr(knowledge, 'query', fail)
    response = client.post('/knowledge/query', headers=auth_headers, json={'question':'q'})
    assert response.status_code == status
    assert 'secret' not in response.text and 'answer' not in response.json()
