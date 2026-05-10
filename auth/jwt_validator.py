# auth/jwt_validator.py
import logging
from typing import Optional

import httpx
from jose import jwt, JWTError
from fastapi import HTTPException, status

from config.keycloak import KeycloakConfig

logger = logging.getLogger(__name__)


class JWTValidator:
    def __init__(self, config: KeycloakConfig):
        self.config = config
        self._jwks: Optional[dict] = None
        self._issuer = config.issuer_uri

    def _fetch_jwks(self) -> dict:
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(self.config.jwks_url)
                response.raise_for_status()
                self._jwks = response.json()
                logger.info(f"JWKS fetched from {self.config.jwks_url}")
                return self._jwks
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            raise

    def _get_jwks(self) -> dict:
        if self._jwks is None:
            return self._fetch_jwks()
        return self._jwks

    def refresh_jwks(self) -> None:
        self._jwks = None
        self._fetch_jwks()

    def _get_signing_key(self, token: str) -> dict:
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token header: {e}",
            )

        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token header missing 'kid'",
            )

        jwks_data = self._get_jwks()
        for key in jwks_data.get("keys", []):
            if key.get("kid") == kid:
                return key

        logger.warning(f"Signing key '{kid}' not found in cache, refreshing JWKS")
        self.refresh_jwks()
        jwks_data = self._get_jwks()

        for key in jwks_data.get("keys", []):
            if key.get("kid") == kid:
                return key

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Signing key '{kid}' not found in JWKS",
        )

    def validate_token(self, token: str) -> dict:
        signing_key = self._get_signing_key(token)

        try:
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "RS384", "RS512", "PS256", "PS384", "PS512"],
                issuer=self._issuer,
                audience=self.config.client_id,
                options={
                    "verify_signature": True,
                    "verify_aud": False,  # можно временно отключить, если BFF шлёт токены не для auth
                    "verify_iss": True,
                    "verify_exp": True,
                },
            )
            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.JWTClaimsError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token claims: {e}",
            )
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {e}",
            )