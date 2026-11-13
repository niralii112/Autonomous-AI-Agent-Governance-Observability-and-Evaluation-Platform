
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import type { UserRole } from "../api/auth";

type ProtectedRouteProps = {
    allowedRoles?: UserRole[];
};

export default function ProtectedRoute({
    allowedRoles,
}: ProtectedRouteProps) {
    const location = useLocation();
    const {
        isAuthenticated,
        isLoading,
        hasRole,
    } = useAuth();

    if (isLoading) {
        return <div className="p-8">Loading...</div>;
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace state={{ from: location }} />;
    }

    if (allowedRoles && !hasRole(allowedRoles)) {
        return (
            <div className="p-8">
                <h1 className="text-2xl font-bold">
                    Access denied
                </h1>
                <p>
                    You do not have permission to access this page.
                </p>
            </div>
        );
    }

    return <Outlet />;
}
