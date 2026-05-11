// Central API base URL — change this ONE value to switch between local and ngrok
// Local dev:  export const API = ''
// ngrok demo: export const API = 'https://your-url.ngrok-free.app'
export const API = import.meta.env.VITE_API_URL || '';
