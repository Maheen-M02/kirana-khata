/** Static marketing site: exported to plain HTML (site/out) and served from any CDN. */
const nextConfig = {
  output: "export",
  reactStrictMode: true,
  poweredByHeader: false,
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
