/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  async headers() {
    return [
      {
        // The Sylva scene runs in a `sandbox="allow-scripts"` iframe (origin
        // `null`), and its authored stylesheet pulls `inner-green-assets/
        // lexend-latin.woff2` by relative URL. Fonts are always CORS-checked,
        // so the null-origin document needs an explicit ACAO to fetch it.
        source: "/inner-green-assets/:path*",
        headers: [{ key: "Access-Control-Allow-Origin", value: "*" }],
      },
    ];
  },
};

export default nextConfig;
