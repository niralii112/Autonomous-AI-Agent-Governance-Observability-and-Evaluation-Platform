
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

export default function Login() {
    const navigate = useNavigate();
    const { signIn, isLoading } = useAuth();

    const [username, setUsername] = useState("demo_admin");
    const [password, setPassword] = useState("demo123");
    const [error, setError] = useState("");

    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        setError("");

        try {
            await signIn({ username, password });
            navigate("/", { replace: true });
        } catch (err) {
            setError(
                err instanceof Error
                    ? err.message
                    : "Unable to sign in"
            );
        }
    }

    return (
        <div className="min-h-screen bg-[#FFE3CE] flex items-center justify-center p-6">
            <div className="w-full max-w-md rounded-[32px] bg-[#1A1A1A] p-10 text-white shadow-2xl">
                <div className="mb-10">
                    <div className="mb-5 inline-flex rounded-full bg-[#F5F87A] px-4 py-2 text-xs font-semibold text-black">
                        AGENT GOVERNANCE
                    </div>

                    <h1 className="text-4xl font-bold tracking-tight">
                        Welcome back.
                    </h1>

                    <p className="mt-3 text-sm text-white/60">
                        Sign in to your governance workspace.
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                    <div>
                        <label htmlFor="username" className="mb-2 block text-sm">
                            Username
                        </label>

                        <input
                            id="username"
                            autoComplete="username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            required
                            className="w-full rounded-xl border border-white/20 bg-white/10 p-4 outline-none focus:border-[#F5F87A]"
                        />
                    </div>

                    <div>
                        <label htmlFor="password" className="mb-2 block text-sm">
                            Password
                        </label>

                        <input
                            id="password"
                            type="password"
                            autoComplete="current-password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                            className="w-full rounded-xl border border-white/20 bg-white/10 p-4 outline-none focus:border-[#F5F87A]"
                        />
                    </div>

                    {error && (
                        <p role="alert" className="text-sm text-red-300">
                            {error}
                        </p>
                    )}

                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full rounded-xl bg-[#F5F87A] p-4 font-bold text-black transition hover:opacity-90 disabled:opacity-50"
                    >
                        {isLoading ? "Signing in..." : "Sign in"}
                    </button>
                </form>
            </div>
        </div>
    );
}
