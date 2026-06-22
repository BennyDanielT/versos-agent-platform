"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

// TanStack Query owns all server state: caching, loading/error flags, refetching,
// optimistic updates. We deliberately do NOT hand-roll useEffect+fetch — that path
// drops loading/error/empty handling and reads as junior.
export default function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false },
        },
      }),
  );
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
