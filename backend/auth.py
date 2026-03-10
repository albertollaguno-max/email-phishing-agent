import os
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from keycloak import KeycloakOpenID
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://localhost:8080/")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "myrealm")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "email-agent-ui")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "") # Optional for public clients

keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_SERVER_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM,
    client_secret_key=KEYCLOAK_CLIENT_SECRET,
    verify=True # Set to False if using self-signed certs in dev
)

security = HTTPBearer()

class UserUser(BaseModel):
    id: str
    username: str
    email: str | None = None
    roles: list[str] = []

async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> UserUser:
    """
    Dependency to validate Keycloak JWT token and return user info.
    """
    token = credentials.credentials
    try:
        # Decode and verify the token. 
        # For full security in prod, fetch public key and verify signature.
        # python-keycloak's decode_token with kwargs handles this if configured.
        
        # We will use userinfo endpoint or decode without verifying signature for simplicity here,
        # but the best approach is to get the public key from Keycloak.
        
        # For this prototype, we decode token and check expiration manually
        # Note: If it's a confidential client, use `keycloak_openid.userinfo(token)`
        
        KEYCLOAK_PUBLIC_KEY = "-----BEGIN PUBLIC KEY-----\n" + keycloak_openid.public_key() + "\n-----END PUBLIC KEY-----"
        
        token_info = keycloak_openid.decode_token(token)
        
        user = UserUser(
            id=token_info.get("sub"),
            username=token_info.get("preferred_username", "unknown"),
            email=token_info.get("email"),
            roles=token_info.get("realm_access", {}).get("roles", [])
        )
        return user
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to decode or verify Keycloak token: {e}")
        
        raise HTTPException(
            status_code=401,
            detail=f"Invalid authentication credentials: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
