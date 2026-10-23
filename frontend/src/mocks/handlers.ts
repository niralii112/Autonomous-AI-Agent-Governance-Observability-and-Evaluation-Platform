
import { http, HttpResponse } from "msw";
import type { components } from "../types/generated/api";

type User = components["schemas"]["UserResponse"];
type LoginRequest = components["schemas"]["LoginRequest"];
type TokenResponse = components["schemas"]["TokenResponse"];

const demoUser: User = {
    user_id: "00000000-0000-4000-8000-000000000001",
    username: "demo_admin",
    email: "demo@example.com",
    role: "ADMIN",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    last_login_at: null,
};

const demoToken = "development-mock-token";

export const handlers = [
    http.post("*/api/v1/auth/login", async ({ request }) => {
        const body = (await request.json()) as LoginRequest;

        if (
            body.username !== "demo_admin" ||
            body.password !== "demo123"
        ) {
            return HttpResponse.json(
                {
                    error_code: "AUTH_INVALID_CREDENTIALS",
                    error_message: "Invalid username or password",
                },
                { status: 401 }
            );
        }

        const response: TokenResponse = {
            access_token: demoToken,
            token_type: "bearer",
            expires_in: 3600,
            user: demoUser,
        };

        return HttpResponse.json(response);
    }),

    http.get("*/api/v1/auth/me", ({ request }) => {
        const token = request.headers.get("Authorization");

        if (token !== `Bearer ${demoToken}`) {
            return HttpResponse.json(
                {
                    error_code: "AUTH_MISSING_CREDENTIALS",
                    error_message: "Authentication required",
                },
                { status: 401 }
            );
        }

        return HttpResponse.json(demoUser);
    }),

    http.post("*/api/v1/auth/logout", () => {
        return new HttpResponse(null, { status: 204 });
    }),
];

