export const isDemoMode =
  import.meta.env.DEV && import.meta.env.VITE_ENABLE_MOCKS === "true";
