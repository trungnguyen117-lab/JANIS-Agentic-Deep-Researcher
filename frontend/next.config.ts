import type { NextConfig } from "next";
import { readFileSync } from "fs";
import { resolve } from "path";

// Load .env from project root (parent directory) for Next.js
// Next.js will automatically load NEXT_PUBLIC_* vars from .env files
// This ensures it reads from root .env instead of frontend/.env
const rootEnvPath = resolve(__dirname, "../.env");
let rootEnv: Record<string, string> = {};

try {
  const envContent = readFileSync(rootEnvPath, "utf-8");
  envContent.split("\n").forEach((line) => {
    const trimmed = line.trim();
    if (trimmed && !trimmed.startsWith("#") && trimmed.includes("=")) {
      const [key, ...valueParts] = trimmed.split("=");
      if (key.startsWith("NEXT_PUBLIC_")) {
        rootEnv[key] = valueParts.join("=").replace(/^["']|["']$/g, "");
      }
    }
  });
} catch (error) {
  // .env file doesn't exist yet, that's okay
  console.warn("Root .env file not found, using default values");
}

const nextConfig: NextConfig = {
  env: rootEnv,
  eslint: {
    // Allow production builds to succeed even if there are ESLint errors.
    // Local development (`npm run dev`) will still show lint issues.
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
