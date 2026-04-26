'use client'

import { useState, useEffect, useRef } from 'react'
import { Send, Paperclip, Trash2, Sparkles, User, Bot } from 'lucide-react'
import api from '@/lib/api'
import ReactMarkdown from 'react-markdown'
import toast from 'react-hot-toast'
import UploadConfirmModal from '@/components/UploadConfirmModal'
import clsx from 'clsx'
import { useStatusLogs } from '@/hooks/useStatusLogs'

interface Message {
    role: 'user' | 'assistant'
    content: string
    created_at?: string
}

const suggestedPrompts = [
    "💰 How much did I spend this month?",
    "📊 Am I over budget anywhere?",
    "🔍 What are my biggest expenses?",
    "⚠️ Any unusual transactions?",
]

export default function ChatPage() {
    const [messages, setMessages] = useState<Message[]>([])
    const { lastLog } = useStatusLogs()
    const [input, setInput] = useState('')
    const [isLoading, setIsLoading] = useState(false)
    const [uploadData, setUploadData] = useState<any>(null)
    const messagesEndRef = useRef<HTMLDivElement>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                const res = await api.get('/api/chat/history')
                setMessages(res.data)
            } catch (err) {
                console.error("Failed to fetch chat history")
            }
        }
        fetchHistory()
    }, [])

    useEffect(scrollToBottom, [messages])

    const handleSend = async (text: string = input) => {
        if (!text.trim() || isLoading) return

        const userMsg: Message = { role: 'user', content: text }
        setMessages(prev => [...prev, userMsg])
        setInput('')
        setIsLoading(true)

        try {
            const res = await api.post('/api/chat', { message: text })
            // Strip any "Assistant: " or "Assistant: " prefix if the model adds it
            const cleanResponse = res.data.response.replace(/^(Assistant:\s*|Assistant:\s*)/i, '')
            setMessages(prev => [...prev, { role: 'assistant', content: cleanResponse }])
        } catch (err) {
            toast.error("I'm having a bit of trouble right now.")
        } finally {
            setIsLoading(false)
        }
    }

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (!file) return

        const formData = new FormData()
        formData.append('file', file)

        const loading = toast.loading('Reading document...')
        setIsLoading(true)
        try {
            const res = await api.post('/api/upload', formData)
            setUploadData(res.data)
            toast.success('Done!', { id: loading })
        } catch (err) {
            toast.error('Failed to read the file', { id: loading })
        } finally {
            setIsLoading(false)
            if (fileInputRef.current) fileInputRef.current.value = ''
        }
    }

    return (
        <div className="flex flex-col h-screen bg-[#ffffff] text-[#171717] overflow-hidden">
            {/* Header */}
            <header className="h-16 border-b border-[#e5e5e5] flex items-center justify-between px-8 shrink-0 bg-white/80 backdrop-blur-md z-10">
                <div className="flex items-center gap-3">
                    <span className="text-xs font-bold uppercase tracking-[0.2em] text-[#a3a3a3]">Finn Assistant</span>
                </div>
                <div className="flex gap-4">
                    <button 
                        onClick={async () => {
                            try {
                                await api.delete('/api/chat/history')
                                setMessages([])
                                toast.success("Session ended")
                            } catch (err) {
                                toast.error("Could not end session")
                            }
                        }} 
                        className="text-[#a3a3a3] hover:text-[#ef4444] p-1.5 rounded-xl transition-all"
                    >
                        <Trash2 size={18} />
                    </button>
                </div>
            </header>

            {/* Messages Area */}
            <div className="flex-1 overflow-y-auto pt-12 pb-48">
                <div className="max-w-4xl mx-auto px-6 space-y-16">
                    {messages.length === 0 && (
                        <div className="mt-24 text-center space-y-10 animate-in fade-in zoom-in-95 duration-1000">
                            <div className="mx-auto w-16 h-16 rounded-[2rem] bg-[#fdf5eb] flex items-center justify-center text-[#cc9966]">
                                <Sparkles size={32} />
                            </div>
                            <h2 className="text-4xl font-bold tracking-tight text-[#171717]">How can I help you?</h2>
                            <div className="flex flex-wrap justify-center gap-3 max-w-2xl mx-auto">
                                {suggestedPrompts.map(p => (
                                    <button 
                                        key={p} 
                                        onClick={() => handleSend(p)}
                                        className="px-6 py-3 rounded-2xl border border-[#e5e5e5] bg-white hover:border-[#cc9966] hover:bg-[#fdf5eb] transition-all text-sm font-medium text-[#525252] shadow-sm hover:shadow-md"
                                    >
                                        {p}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {messages.map((msg, idx) => (
                        <div key={idx} className="flex gap-8 group animate-in fade-in slide-in-from-bottom-6 duration-700">
                            <div className={clsx(
                                "w-10 h-10 rounded-2xl shrink-0 flex items-center justify-center border transition-all",
                                msg.role === 'user' ? "bg-white border-[#e5e5e5] text-[#737373]" : "bg-[#fdf5eb] border-[#f4e2cc] text-[#cc9966]"
                            )}>
                                {msg.role === 'user' ? <User size={20} /> : <Bot size={20} />}
                            </div>
                            <div className="flex-1 space-y-3 pt-1">
                                <div className="text-[10px] font-bold uppercase tracking-widest text-[#a3a3a3]">
                                    {msg.role === 'user' ? 'You' : 'Finn'}
                                </div>
                                <div className="prose prose-zinc prose-sm max-w-none leading-relaxed text-[#171717]">
                                    <ReactMarkdown 
                                        components={{
                                            p: ({...props}) => <p className="mb-4 text-[15px]" {...props} />,
                                            ul: ({...props}) => <ul className="list-disc ml-4 space-y-2 mb-4" {...props} />,
                                            li: ({...props}) => <li className="text-[15px]" {...props} />
                                        }}
                                    >
                                        {msg.content}
                                    </ReactMarkdown>
                                </div>
                            </div>
                        </div>
                    ))}

                    {isLoading && (
                        <div className="flex gap-8 animate-in fade-in duration-500">
                            <div className="w-10 h-10 rounded-2xl bg-[#fdf5eb] border border-[#f4e2cc] flex items-center justify-center text-[#cc9966]">
                                <Bot size={20} className="animate-bounce" />
                            </div>
                            <div className="flex-1 pt-1 space-y-4">
                                <div className="flex flex-col gap-3">
                                    <div className="flex items-center gap-2 px-4 py-2 bg-[#fdf5eb] border border-[#f4e2cc] rounded-2xl w-fit animate-in slide-in-from-left-2 duration-300">
                                        <span className="text-sm font-bold text-[#cc9966]">{lastLog || "Analyzing..."}</span>
                                    </div>
                                    <div className="flex gap-1.5 h-1 items-center ml-2">
                                        <div className="w-1 h-1 bg-[#cc9966]/20 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                                        <div className="w-1 h-1 bg-[#cc9966]/20 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                                        <div className="w-1 h-1 bg-[#cc9966]/20 rounded-full animate-bounce"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>
            </div>

            {/* Floating Input Area */}
            <div className="fixed bottom-0 left-0 right-0 md:left-auto md:w-[calc(100%-288px)] bg-gradient-to-t from-white via-white/95 to-transparent p-8 pb-12 z-20">
                <div className="max-w-4xl mx-auto">
                    <div className="bg-white border border-[#e5e5e5] rounded-[2rem] shadow-2xl shadow-black/5 p-3 pr-6 flex items-end gap-3 ring-1 ring-black/[0.02]">
                        <button 
                            onClick={() => fileInputRef.current?.click()}
                            className="p-4 text-[#a3a3a3] hover:text-[#cc9966] transition-all hover:bg-[#fdf5eb] rounded-2xl"
                        >
                            <Paperclip size={22} />
                        </button>
                        <input type="file" hidden ref={fileInputRef} onChange={handleFileUpload} accept="image/*,application/pdf" />
                        
                        <textarea 
                            rows={1}
                            value={input}
                            onChange={e => setInput(e.target.value)}
                            onKeyDown={e => { if(e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                            placeholder="Ask Finn anything about your finances..."
                            className="flex-1 bg-transparent border-none focus:ring-0 resize-none py-4 text-[15px] outline-none placeholder:text-[#d4d4d4]"
                        />
                        
                        <button 
                            onClick={() => handleSend()}
                            disabled={!input.trim() || isLoading}
                            className="p-3 mb-1.5 bg-[#cc9966] text-white rounded-2xl disabled:bg-[#f5f5f5] disabled:text-[#d4d4d4] transition-all hover:scale-105 active:scale-95 shadow-lg shadow-[#cc9966]/20"
                        >
                            <Send size={20} />
                        </button>
                    </div>
                    <p className="text-[11px] text-center mt-5 text-[#a3a3a3] font-medium tracking-wide">
                        Powered by Finn AI • High-precision financial analysis
                    </p>
                </div>
            </div>

            {uploadData && (
                <UploadConfirmModal 
                    isOpen={!!uploadData} 
                    onClose={() => setUploadData(null)}
                    extractedData={uploadData}
                    onSaved={() => handleSend("I've uploaded those transactions.")}
                />
            )}
        </div>
    )
}
