
import {
    createContext,
    useCallback,
    useContext,
    useState,
    type ReactNode,
} from "react";

import {
    login,
    logout,
    getCurrentUser,
    clearAuthToken,
    type AuthUser,
    type LoginRequest,
    type UserRole,
} from "../api/auth";

type AuthContextType = {
    user: AuthUser | null;
    isAuthenticated: boolean;
    isLoading: boolean;
    signIn: (credentials: LoginRequest) => Promise<void>;
    signOut: () => Promise<void>;
    refreshUser: () => Promise<void>;
    hasRole: (roles: UserRole[]) => boolean;
};

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({
    children,
}: {
    children: ReactNode;
}) {
    const [user, setUser] = useState<AuthUser | null>(null);
    const [isLoading, setIsLoading] = useState(false);

    const signIn = useCallback(
        async (credentials: LoginRequest) => {
            setIsLoading(true);

            try {
                const result = await login(credentials);
                setUser(result.user);
            } finally {
                setIsLoading(false);
            }
        },
        []
    );

    const signOut = useCallback(async () => {
        setIsLoading(true);

        try {
            await logout();
        } finally {
            setUser(null);
            setIsLoading(false);
        }
    }, []);

    const refreshUser = useCallback(async () => {
        setIsLoading(true);

        try {
            const currentUser = await getCurrentUser();
            setUser(currentUser);
        } catch (error) {
            clearAuthToken();
            setUser(null);
            throw error;
        } finally {
            setIsLoading(false);
        }
    }, []);

    const hasRole = (roles: UserRole[]) => {
        return !!user && roles.includes(user.role);
    };

    return (
        <AuthContext.Provider
            value={{
                user,
                isAuthenticated: !!user,
                isLoading,
                signIn,
                signOut,
                refreshUser,
                hasRole,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
}

export function useAuthContext() {
    const context = useContext(AuthContext);

    if (!context) {
        throw new Error(
            "useAuthContext must be used inside AuthProvider"
        );
    }

    return context;
}
