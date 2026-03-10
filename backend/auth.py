import os
import logging
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from keycloak import KeycloakOpenID
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "myrealm")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "email-agent-ui")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "")

REQUIRED_ROLE = "emailphisingIA"

keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_SERVER_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM,
    client_secret_key=KEYCLOAK_CLIENT_SECRET,
    verify=True
)

security = HTTPBearer()

class UserUser(BaseModel):
    id: str
    username: str
    email: str | None = None
    roles: list[str] = []

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> UserUser:
    """Validate Keycloak JWT and enforce required role."""
    token = credentials.credentials
    try:
        token_info = keycloak_openid.decode_token(token)

        realm_roles = token_info.get("realm_access", {}).get("roles", [])
        client_roles = []
        for client_data in token_info.get("resource_access", {}).values():
            client_roles.extend(client_data.get("roles", []))
        all_roles = list(set(realm_roles + client_roles))

        user = UserUser(
            id=token_info.get("sub"),
            username=token_info.get("preferred_username", "unknown"),
            email=token_info.get("email"),
            roles=all_roles
        )

        if REQUIRED_ROLE not in all_roles:
            logger.warning(f"Access denied for '{user.username}' — roles: {all_roles}")
            raise HTTPException(status_code=403, detail=f"Missing required role '{REQUIRED_ROLE}'")

        return user

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        raise HTTPException(status_code=401, detail=str(e), headers={"WWW-Authenticate": "Bearer"})
