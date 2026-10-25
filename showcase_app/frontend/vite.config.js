import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { execSync } from 'child_process'

// Backend host resolution:
// - Default: localhost (backend running natively, same machine as Vite)
// - Set BACKEND_HOST=wsl to resolve the WSL2 IP (when backend runs in WSL2
//   and Vite runs on Windows).
// - Or set BACKEND_HOST=<ip-or-host> directly.
let backendHost = 'localhost'
const override = process.env.BACKEND_HOST
if (override === 'wsl') {
  try {
    const wslIp = execSync('wsl -d Ubuntu bash -lc "hostname -I"', { encoding: 'utf-8' }).trim().split(/\s+/)[0]
    if (wslIp) backendHost = wslIp
  } catch {
    // wsl command unavailable — stay on localhost
  }
} else if (override) {
  backendHost = override
}

const API_TARGET = `http://${backendHost}:7331`
const WS_TARGET = `ws://${backendHost}:7331`

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5174,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/health': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/ws': {
        target: WS_TARGET,
        ws: true,
      },
    },
  },
})
