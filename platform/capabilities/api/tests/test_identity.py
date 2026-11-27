import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from platform_api.identity import TokenVerifier, Unauthenticated

ISSUER = "http://localhost:8180/realms/platform"


@pytest.fixture
def keys():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048), \
        rsa.generate_private_key(public_exponent=65537, key_size=2048)


def verifier(public_key):
    v = TokenVerifier(ISSUER, "platform", "http://keycloak.invalid/certs")

    class Key:
        key = public_key

    v._keys.get_signing_key_from_jwt = lambda token: Key()
    return v


def token(private_key, **claims):
    now = int(time.time())
    body = {"iss": ISSUER, "aud": ["platform", "account"], "azp": "claude-code", "preferred_username": "marta",
            "groups": ["checkout"], "iat": now, "exp": now + 300, **claims}
    return jwt.encode(body, private_key, algorithm="RS256")


def test_accepts_a_keycloak_token_for_the_platform(keys):
    signer, _ = keys
    assert verifier(signer.public_key()).claims(token(signer))["azp"] == "claude-code"


@pytest.mark.parametrize("claims", [
    {"iss": "http://evil/realms/platform"},
    {"aud": "another-service"},
    {"exp": int(time.time()) - 120},
])
def test_rejects_tokens_for_other_issuers_audiences_or_expired(keys, claims):
    signer, _ = keys
    with pytest.raises(Unauthenticated):
        verifier(signer.public_key()).claims(token(signer, **claims))


def test_rejects_tokens_signed_by_someone_else(keys):
    signer, other = keys
    with pytest.raises(Unauthenticated):
        verifier(signer.public_key()).claims(token(other))
