import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    // CI/older hardware can take longer to start each isolated worker;
    // keep per-test budgets generous without changing assertions.
    testTimeout: 20000,
    hookTimeout: 20000,
  },
})
