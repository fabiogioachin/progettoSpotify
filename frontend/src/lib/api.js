import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Interceptor: retry su 429 (solo se Retry-After <= 30s), redirect a login su 401
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config

    if (error.response?.status === 429 && (!config._retryCount || config._retryCount < 2)) {
      const retryAfter = parseInt(error.response.headers['retry-after'] || '0', 10)
      // Se Spotify è in ban mode (Retry-After > 30s) non riprovare — mostra errore
      if (retryAfter > 30) return Promise.reject(error)
      config._retryCount = (config._retryCount || 0) + 1
      const delay = retryAfter > 0 ? retryAfter * 1000 : 1000 * config._retryCount
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
