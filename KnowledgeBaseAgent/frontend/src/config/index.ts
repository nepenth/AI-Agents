interface Config {
  apiUrl: string
  wsUrl: string
  environment: 'development' | 'staging' | 'production'
}

const getConfig = (): Config => {
  const isDevelopment = import.meta.env.DEV
  const apiBaseUrl = import.meta.env.VITE_API_URL || (isDevelopment ? 'http://localhost:8000' : '')
  const wsBaseUrl = import.meta.env.VITE_WS_URL || (isDevelopment ? 'ws://localhost:8000' : '')

  return {
    apiUrl: apiBaseUrl,
    wsUrl: `${wsBaseUrl}/api/v1/ws`,
    environment: import.meta.env.MODE as Config['environment'] || 'development',
  }
}

export const config = getConfig()