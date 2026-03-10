import keycloak from "./keycloak";

const BASE_URL = "/api";

export const fetchWithAuth = async (endpoint: string, options: RequestInit = {}) => {
    // Attempt to refresh the token if it expires in less than 30 seconds
    try {
        if (keycloak.authenticated) {
            await keycloak.updateToken(30);
        }
    } catch (error) {
        console.error("Failed to refresh token, forcing login again", error);
        keycloak.login();
        throw new Error("Session expired");
    }

    if (keycloak.token) {
        options.headers = {
            ...options.headers,
            Authorization: `Bearer ${keycloak.token}`,
            "Content-Type": "application/json"
        };
    } else {
        options.headers = {
            ...options.headers,
            "Content-Type": "application/json"
        };
    }

    const response = await fetch(`${BASE_URL}${endpoint}`, options);

    if (!response.ok) {
        if (response.status === 401) {
            keycloak.login();
        }
        throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    return response.json();
};
