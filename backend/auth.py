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

# Required Keycloak realm role to access the application
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
    has_required_role: bool = False


def _decode_and_extract(token: str) -> UserUser:
    """Decode JWT server-side and extract user info with all roles."""
    token_info = keycloak_openid.decode_token(token)

    realm_roles = token_info.get("realm_access", {}).get("roles", [])
    # Collect roles from ALL clients in resource_access
    all_client_roles = []
    for client_data in token_info.get("resource_access", {}).values():
        all_client_roles.extend(client_data.get("roles", []))
    all_roles = list(set(realm_roles + all_client_roles))

    user = UserUser(
        id=token_info.get("sub"),
        username=token_info.get("preferred_username", "unknown"),
        email=token_info.get("email"),
        roles=all_roles,
        has_required_role=REQUIRED_ROLE in all_roles,
    )
    return user


async def get_current_user_no_role(credentials: HTTPAuthorizationCredentials = Security(security)) -> UserUser:
    """Validate token and return user info WITHOUT enforcing role (for /auth/me)."""
    try:
        return _decode_and_extract(credentials.credentials)
    except Exception as e:
        logger.error(f"Failed to decode Keycloak token: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> UserUser:
    """Validate token, extract user, and ENFORCE required role."""
    try:
        user = _decode_and_extract(credentials.credentials)
    except Exception as e:
        logger.error(f"Failed to decode Keycloak token: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.has_required_role:
        logger.warning(
            f"Access denied for user '{user.username}' — missing required role '{REQUIRED_ROLE}'. "
            f"User roles: {user.roles}"
        )
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: you need the '{REQUIRED_ROLE}' role to use this application.",
        )

    return user
