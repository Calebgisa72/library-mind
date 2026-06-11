/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a self-contained server bundle (.next/standalone) so the Docker
  // runtime image needs neither node_modules nor the Next.js CLI.
  output: "standalone",
  // The frontend talks to the FastAPI backend over CORS in development.
  // In production you can proxy /api/* to the backend by configuring rewrites.
  async rewrites() {
    const backend = process.env.BACKEND_INTERNAL_URL;
    if (!backend) return [];
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backend}/:path*`,
      },
    ];
  },
};

export default nextConfig;
