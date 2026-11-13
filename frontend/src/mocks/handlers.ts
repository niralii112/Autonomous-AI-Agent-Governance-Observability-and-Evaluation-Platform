import { http, HttpResponse } from "msw";
import type { components } from "../types/generated/api";

type User = components["schemas"]["UserResponse"];
type LoginRequest = components["schemas"]["LoginRequest"];
type TokenResponse = components["schemas"]["TokenResponse"];

const accounts = {
  demo_admin: "ADMIN",
  demo_reviewer: "REVIEWER",
  demo_viewer: "VIEWER",
} as const;

const users: User[] = Object.entries(accounts).map(([username, role], index) => ({
  user_id: `00000000-0000-4000-8000-00000000000${index + 1}`,
  username,
  email: `${username}@example.com`,
  role,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
}));

function tokenFor(user: User) {
  return `development-mock-token-${user.username}`;
}

export const handlers = [
  http.post("*/api/v1/auth/login", async ({ request }) => {
    const body = await request.json() as LoginRequest;
    const user = users.find((item) => item.username === body.username);
    if (!user || body.password !== "demo123") {
      return HttpResponse.json({
        error_code: "AUTH_INVALID_CREDENTIALS",
        error_message: "Invalid username or password",
      }, { status: 401 });
    }
    const response: TokenResponse = {
      access_token: tokenFor(user),
      token_type: "bearer",
      expires_in: 3600,
      user,
    };
    return HttpResponse.json(response);
  }),
  http.get("*/api/v1/auth/me", ({ request }) => {
    const user = users.find((item) => request.headers.get("Authorization") === `Bearer ${tokenFor(item)}`);
    if (!user) {
      return HttpResponse.json({
        error_code: "AUTH_MISSING_CREDENTIALS",
        error_message: "Authentication required",
      }, { status: 401 });
    }
    return HttpResponse.json(user);
  }),
  http.post("*/api/v1/auth/logout", () => new HttpResponse(null, { status: 204 })),
];
