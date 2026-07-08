import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output (`.next/standalone`) is ONLY for the Docker image (`node server.js`).
  // Amplify's managed Next.js build wants the default output, so gate it on the Docker build.
  ...(process.env.DOCKER_BUILD ? { output: "standalone" as const } : {}),
};

export default nextConfig;
