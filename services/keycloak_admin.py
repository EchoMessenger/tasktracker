# services/keycloak_admin.py
import logging
from typing import Optional
import httpx

from config.keycloak import KeycloakConfig
from models.user import UserRole

logger = logging.getLogger(__name__)


class KeycloakAdminClient:
    def __init__(self, config: KeycloakConfig):
        self.config = config
        self._admin_token: Optional[str] = None

    def _get_admin_token(self) -> str:
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.post(
                    self.config.token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.config.client_id,
                        "client_secret": self.config.client_secret,
                    },
                )
                response.raise_for_status()

                token_data = response.json()
                access_token = token_data.get("access_token")
                if not access_token:
                    raise RuntimeError("Keycloak token response does not contain access_token")

                self._admin_token = access_token
                logger.info("Keycloak admin token obtained successfully")
                return access_token

        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to obtain Keycloak token: {e.response.status_code} {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Failed to obtain Keycloak token: {e}")
            raise

    def _get_headers(self) -> dict:
        token = self._get_admin_token()
        return {"Authorization": f"Bearer {token}"}

    def get_all_users(self, max_users: int = 1000) -> list[dict]:
        all_users = []
        first = 0
        page_size = 100

        with httpx.Client(timeout=30.0) as client:
            headers = self._get_headers()

            while first < max_users:
                response = client.get(
                    self.config.admin_users_url,
                    headers=headers,
                    params={
                        "first": first,
                        "max": page_size,
                        "briefRepresentation": False,
                    },
                )
                response.raise_for_status()

                page = response.json()
                if not page:
                    break

                all_users.extend(page)
                first += page_size

                if len(page) < page_size:
                    break

        logger.info(f"Fetched {len(all_users)} users from Keycloak")
        return all_users

    def get_user_roles(self, user_id: str) -> list[str]:
        roles = []

        with httpx.Client(timeout=15.0) as client:
            headers = self._get_headers()

            # realm roles
            realm_url = f"{self.config.server_url}/admin/realms/{self.config.realm}/users/{user_id}/role-mappings/realm"
            realm_resp = client.get(realm_url, headers=headers)
            if realm_resp.status_code == 200:
                roles.extend([r["name"] for r in realm_resp.json()])

            # client roles for current client
            clients_url = f"{self.config.server_url}/admin/realms/{self.config.realm}/clients"
            clients_resp = client.get(clients_url, headers=headers)
            clients_resp.raise_for_status()

            target_client = None
            for client_obj in clients_resp.json():
                if client_obj.get("clientId") == self.config.client_id:
                    target_client = client_obj
                    break

            if target_client:
                client_uuid = target_client["id"]
                client_roles_url = (
                    f"{self.config.server_url}/admin/realms/{self.config.realm}"
                    f"/users/{user_id}/role-mappings/clients/{client_uuid}"
                )
                client_roles_resp = client.get(client_roles_url, headers=headers)
                if client_roles_resp.status_code == 200:
                    roles.extend([r["name"] for r in client_roles_resp.json()])

        return list(set(roles))

    @staticmethod
    def map_keycloak_role(keycloak_roles: list[str]) -> UserRole:
        if "admin" in keycloak_roles:
            return UserRole.ADMIN
        if "manager" in keycloak_roles:
            return UserRole.MANAGER
        return UserRole.USER

    @staticmethod
    def build_full_name(keycloak_user: dict) -> str:
        first_name = keycloak_user.get("firstName", "") or ""
        last_name = keycloak_user.get("lastName", "") or ""
        full_name = f"{first_name} {last_name}".strip()
        return full_name or keycloak_user.get("username", "")