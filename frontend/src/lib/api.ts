import axios from 'axios'

const api = axios.create({ 
    baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000' 
})

export default api

export const CATEGORIES = [
  "Food", "Transport", "Utilities", "Shopping", "Entertainment",
  "Healthcare", "Education", "Miscellaneous"
]

export const CATEGORY_EMOJI: Record<string, string> = {
  "Food": "🍽️", "Transport": "🚗", "Utilities": "⚡", "Shopping": "🛍️",
  "Entertainment": "🎬", "Healthcare": "💊", "Education": "📚", "Miscellaneous": "📦"
}
