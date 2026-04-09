# config/keycloak.py
import os
from dataclasses import dataclass


@dataclass
class KeycloakConfig:
    issuer_uri: str
    client_id: str
    client_secret: str
    admin_username: str | None = None
    admin_password: str | None = None

    @property
    def jwks_url(self) -> str:
        return f"{self.issuer_uri}/protocol/openid-connect/certs"

    @property
    def token_url(self) -> str:
        return f"{self.issuer_uri}/protocol/openid-connect/token"

    @property
    def userinfo_url(self) -> str:
        return f"{self.issuer_uri}/protocol/openid-connect/userinfo"

    @property
    def realm(self) -> str:
        return self.issuer_uri.rstrip("/").split("/")[-1]

    @property
    def server_url(self) -> str:
        """
        Например:
        issuer_uri=https://auth.echo-messenger.ru/realms/echo
        server_url=https://auth.echo-messenger.ru
        """
        marker = "/realms/"
        if marker in self.issuer_uri:
            return self.issuer_uri.split(marker)[0]
        return self.issuer_uri

    @property
    def admin_users_url(self) -> str:
        return f"{self.server_url}/admin/realms/{self.realm}/users"

    @classmethod
    def from_env(cls) -> "KeycloakConfig":
        issuer_uri = os.getenv("KEYCLOAK_ISSUER_URI")
        client_id = os.getenv("KEYCLOAK_CLIENT_ID")
        client_secret = os.getenv("KEYCLOAK_CLIENT_SECRET", "")

        if not issuer_uri:
            raise ValueError("KEYCLOAK_ISSUER_URI is not set")
        if not client_id:
            raise ValueError("KEYCLOAK_CLIENT_ID is not set")

        return cls(
            issuer_uri=issuer_uri.rstrip("/"),
            client_id=client_id,
            client_secret=client_secret,
            admin_username=os.getenv("KEYCLOAK_ADMIN_USERNAME"),
            admin_password=os.getenv("KEYCLOAK_ADMIN_PASSWORD"),
        )