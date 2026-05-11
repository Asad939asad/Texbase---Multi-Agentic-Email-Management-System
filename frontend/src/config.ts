// Central API base URL — change this ONE value to switch between local and ngrok
// Local dev:  export const API = 'http://localhost:8000'
// ngrok demo: export const API = 'https://your-url.ngrok-free.app'
export const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
