/** @type {import('next').NextConfig} */
const FLASK_API = process.env.FLASK_API_URL ?? "http://127.0.0.1:5000";

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${FLASK_API}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
