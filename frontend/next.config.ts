import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export for Amplify. Next 16's cacheComponents flag turns on Partial
  // Prerendering, which cannot be combined with output: "export".
  output: "export",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
