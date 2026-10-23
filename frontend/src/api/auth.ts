
import type { components } from "../types/generated/api";
import { typedApi } from "./functions";

export type LoginRequest = components["schemas"]["LoginRequest"];
export type TokenResponse = components["schemas"]["TokenResponse"];
export type AuthUser = components["schemas"]["UserResponse"];
export type UserRole = components["schemas"]["UserRole"];

let accessToken: string | null = null;
let tokenExpiresAt = 0;

export function setAuthToken(
    token: string,
    expiresIn: number
) {
    accessToken = token;
    tokenExpiresAt = Date.now() + expiresIn * 1000;
}

export function clearAuthToken() {
    accessToken = null;
    tokenExpiresAt = 0;
}

export function getAuthToken() {
    if (accessToken && Date.now() >= tokenExpiresAt) {
        clearAuthToken();
    }
    return accessToken;
}

export async function login(credentials: LoginRequest) {
    const { data, error } = await typedApi.POST(
        "/api/v1/auth/login",
        { body: credentials }
    );

    if (error || !data) {
        throw new Error(
            error?.error_message ?? "Login failed"
        );
    }

    setAuthToken(data.access_token, data.expires_in);
    return data;
}

export async function getCurrentUser(): Promise<AuthUser> {
    const { data, error } = await typedApi.GET(
        "/api/v1/auth/me"
    );

    if (error || !data) {
        throw new Error(
            error?.error_message ?? "Unable to load user"
        );
    }

    return data;
}

export async function logout() {
    try {
        const { error } = await typedApi.POST(
            "/api/v1/auth/logout"
        );

        if (error) {
            throw new Error(
                error.error_message ?? "Logout failed"
            );
        }
    } finally {
        clearAuthToken();
    }
}
