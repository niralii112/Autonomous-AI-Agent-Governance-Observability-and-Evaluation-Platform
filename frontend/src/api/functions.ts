
import createClient from "openapi-fetch";
import type { paths } from "../types/generated/api";
import { operationIds } from "./operations";
import { getAuthToken } from "./auth";

export const typedApi = createClient<paths>({
    baseUrl:
        import.meta.env.VITE_API_BASE_URL ||
        "http://localhost:8000",
});

typedApi.use({
    async onRequest({ request }) {
        const token = getAuthToken();

        if (token) {
            request.headers.set(
                "Authorization",
                `Bearer ${token}`
            );
        }

        return request;
    },
});

export { operationIds };
export type ApiPaths = paths;
