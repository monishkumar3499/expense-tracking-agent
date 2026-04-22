import axios from 'axios'

const api = axios.create({ 
    baseURL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000' 
})

export default api

export const CATEGORIES = [
  "Food & Dining", "Transport", "Utilities", "Shopping", "Entertainment",
  "Healthcare", "Education", "Subscriptions", "Travel", "Groceries", "Miscellaneous"
]

export const CATEGORY_EMOJI: Record<string, string> = {
  "Food & Dining": "🍽️", "Transport": "🚗", "Utilities": "⚡", "Shopping": "🛍️",
  "Entertainment": "🎬", "Healthcare": "💊", "Education": "📚", "Subscriptions": "🔄",
  "Travel": "✈️", "Groceries": "🛒", "Miscellaneous": "📦"
}
