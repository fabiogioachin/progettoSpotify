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
    const status = error.response?.status
    const data = error.response?.data

    if (status === 429) {
      const retryAfter = parseFloat(error.response.headers['retry-after'] || '0')

      // Throttle preventivo del backend — mostra countdown al frontend
      if (data?.detail?.throttled || data?.throttled) {
        const waitSeconds = data?.detail?.retry_after || retryAfter || 5
        // Emetti evento per il countdown UI
        window.dispatchEvent(new CustomEvent('api:throttle', {
          detail: { retryAfter: waitSeconds, url: config.url }
        }))
        // Riprova automaticamente dopo il countdown
        await new Promise(resolve => setTimeout(resolve, waitSeconds * 1000))
        return api(config)
      }

      // 429 da Spotify — comportamento esistente
      if (retryAfter > 30) return Promise.reject(error)
      if (!config._retryCount || config._retryCount < 2) {
        config._retryCount = (config._retryCount || 0) + 1
        const delay = retryAfter > 0 ? retryAfter * 1000 : 1000 * config._retryCount
        await new Promise(resolve => setTimeout(resolve, delay))
        return api(config)
      }
    }

    if (status === 401) {
      window.dispatchEvent(new Event('auth:expired'))
    }
    return Promise.reject(error)
  }
)

export default api
