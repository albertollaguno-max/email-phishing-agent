import React from 'react';
import { ReactKeycloakProvider } from '@react-keycloak/web';
import keycloak from '../keycloak';

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    return (
        <ReactKeycloakProvider
            authClient={keycloak}
            initOptions={{
                onLoad: 'login-required',
                checkLoginIframe: false,
                pkceMethod: 'S256',
            }}
        >
            {children}
        </ReactKeycloakProvider>
    );
};
