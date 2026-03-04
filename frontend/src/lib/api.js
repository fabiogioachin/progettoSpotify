import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Interceptor: retry su 429, redirect a login su 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config

    // Retry on 429 (rate limited) — max 2 retries with exponential backoff
    if (error.response?.status === 429 && (!config._retryCount || config._retryCount < 2)) {
      config._retryCount = (config._retryCount || 0) + 1
      const retryAfter = error.response.headers['retry-after']
      const delay = retryAfter ? parseInt(retryAfter, 10) * 1000 : 1000 * config._retryCount
      await new Promise((resolve) => setTimeout(resolve, delay))
      return api(config)
    }

    if (error.response?.status === 401) {
      window.dispatchEvent(new Event('auth:expired'))
    }
    return Promise.reject(error)
  }
)

export default api
