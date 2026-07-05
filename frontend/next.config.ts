import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server bundle (.next/standalone) so the Docker image can run
  // `node server.js` without the full node_modules — smaller image, faster cold start.
  output: "standalone",
};

export default nextConfig;
