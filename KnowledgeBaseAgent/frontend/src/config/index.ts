interface Config {
  apiUrl: string
  wsUrl: string
  environment: 'development' | 'staging' | 'production'
}

const getConfig = (): Config => {
  const isDevelopment = import.meta.env.DEV
  
  // Get the current host and protocol
  const currentHost = window.location.hostname
  const currentPort = window.location.port
  const currentProtocol = window.location.protocol
  
  // Determine backend URLs based on current location
  let apiBaseUrl = import.meta.env.VITE_API_URL
  let wsBaseUrl = import.meta.env.VITE_WS_URL
  
  if (isDevelopment) {
    // In development, use the Vite dev server proxy
    const devServerBase = `${currentHost}:${currentPort}`
    apiBaseUrl = apiBaseUrl || `${currentProtocol}//${devServerBase}`
    
    // For WebSocket, use the dev server proxy
    const wsProtocol = currentProtocol === 'https:' ? 'wss:' : 'ws:'
    wsBaseUrl = wsBaseUrl || `${wsProtocol}//${devServerBase}`
  }

  return {
    apiUrl: apiBaseUrl || '',
    wsUrl: `${wsBaseUrl}/ws`, // Use the proxy path
    environment: import.meta.env.MODE as Config['environment'] || 'development',
  }
}

export const config = getConfig()