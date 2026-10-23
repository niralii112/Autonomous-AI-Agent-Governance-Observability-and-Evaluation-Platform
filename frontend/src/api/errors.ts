
import axios from "axios";

export function getApiErrorMessage(error: unknown): string {
    if (axios.isAxiosError(error)) {
        if (!error.response) {
            return "Cannot connect to the backend server.";
        }

        const data: unknown = error.response.data;

        if (typeof data === "object" && data !== null) {
            if ("detail" in data && typeof data.detail === "string") {
                return data.detail;
            }

            if ("message" in data && typeof data.message === "string") {
                return data.message;
            }
        }

        return `Request failed with status ${error.response.status}.`;
    }

    if (error instanceof Error) {
        return error.message;
    }

    return "An unexpected error occurred.";
}
