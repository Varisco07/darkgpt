/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // L'endpoint del backend NON viene inlineato nel bundle: e' letto a runtime
  // dal server, cosi' lo stesso build puo' puntare a backend diversi (sviluppo,
  // staging, produzione) senza una nuova build.
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${process.env.DARKGPT_API_URL ?? "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
