import Keycloak from 'keycloak-js';

const keycloakConfig = {
    url: import.meta.env.VITE_KEYCLOAK_URL || 'http://localhost:8080/',
    realm: import.meta.env.VITE_KEYCLOAK_REALM || 'myrealm',
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'email-agent-ui'
};

const keycloak = new Keycloak(keycloakConfig);

export default keycloak;
