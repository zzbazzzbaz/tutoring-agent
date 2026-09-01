/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV === "development";

const nextConfig = {
  output: "standalone",
  experimental: {
    serverActions: {
      bodySizeLimit: "10mb",
    },
  },
  webpack: (config) => {
    config.cache = false;
    return config;
  },
  ...(isDev && {
    async rewrites() {
      return [
        {
          source: "/api/:path*",
          destination: "https://tutoring.chatgqt.top/api/:path*",
        },
        {
          source: "/agent/:path*",
          destination: "https://tutoring.chatgqt.top/agent/:path*",
        },
      ];
    },
  }),
};

export default nextConfig;
