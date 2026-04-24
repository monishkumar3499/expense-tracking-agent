'use client'

import { useStatusLogs } from '@/hooks/useStatusLogs'
import { Sparkles } from 'lucide-react'
import clsx from 'clsx'

export default function StatusBadge() {
    const { lastLog, isActive } = useStatusLogs()

    if (!isActive || !lastLog) return null

    return (
        <div className="flex items-center gap-2 px-4 py-2 bg-[#fdf5eb] border border-[#f4e2cc] rounded-full animate-in fade-in slide-in-from-top-2 duration-700 shadow-sm">
            <span className="text-[12px] font-extrabold text-[#cc9966] whitespace-nowrap tracking-tight leading-none uppercase">{lastLog}</span>
        </div>
    )
}
