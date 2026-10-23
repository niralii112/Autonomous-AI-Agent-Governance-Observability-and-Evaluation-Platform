
import { useQuery } from "@tanstack/react-query";
import { typedApi } from "../api/functions";

export function useCurrentUser() {
    return useQuery({
        queryKey: ["auth", "currentUser"],
        queryFn: async () => {
            const { data, error } = await typedApi.GET(
                "/api/v1/auth/me"
            );

            if (error) {
                throw new Error("Unable to fetch current user");
            }

            return data;
        },
        retry: false,
    });
}

