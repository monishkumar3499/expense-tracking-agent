'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { 
    LayoutDashboard, 
    MessageSquare, 
    ReceiptText, 
    Target, 
    CreditCard, 
    Settings,
    PieChart,
    ChevronLeft,
    ChevronRight,
    Sparkles
} from 'lucide-react'
import { useStatusLogs } from '@/hooks/useStatusLogs'
import StatusBadge from './StatusBadge'
import { useState } from 'react'
import clsx from 'clsx'

const NAV_ITEMS = [
    { label: 'Finn Assistant', icon: MessageSquare, path: '/chat' },
    { label: 'Overview', icon: LayoutDashboard, path: '/dashboard' },
    { label: 'All Transactions', icon: ReceiptText, path: '/transactions' },
    { label: 'Recurring', icon: CreditCard, path: '/subscriptions' },
]

export default function Sidebar() {
    const pathname = usePathname()
    const [isCollapsed, setIsCollapsed] = useState(false)

    return (
        <>
            <aside className={clsx(
                "hidden md:flex flex-col h-screen transition-all duration-500 border-r border-[#e5e5e5] bg-[#fcfcfc] sticky top-0",
                isCollapsed ? "w-20" : "w-72"
            )}>
                <div className="p-8 flex items-center justify-between">
                    {!isCollapsed && (
                        <div className="flex items-center gap-2 group cursor-default">
                            <div className="w-8 h-8 rounded-xl bg-[#cc9966] flex items-center justify-center text-white shadow-lg shadow-[#cc9966]/20">
                                <Sparkles size={18} />
                            </div>
                            <span className="font-bold tracking-tight text-xl text-[#171717]">Finn</span>
                        </div>
                    )}
                    <button 
                        onClick={() => setIsCollapsed(!isCollapsed)}
                        className="p-2 rounded-xl hover:bg-[#f5f5f5] text-[#a3a3a3] transition-all hover:text-[#171717]"
                    >
                        {isCollapsed ? <ChevronRight size={20} /> : <ChevronLeft size={20} />}
                    </button>
                </div>

                <nav className="flex-1 px-4 space-y-2 mt-6">
                    {NAV_ITEMS.map((item) => {
                        const isActive = pathname === item.path
                        return (
                            <Link 
                                key={item.path} 
                                href={item.path}
                                className={clsx(
                                    "flex items-center gap-4 px-4 py-3.5 rounded-2xl transition-all group",
                                    isActive 
                                        ? "bg-white text-[#171717] font-semibold border border-[#e5e5e5] shadow-sm" 
                                        : "text-[#737373] hover:text-[#171717] hover:bg-[#f5f5f5]"
                                )}
                            >
                                <item.icon size={22} className={clsx(isActive ? "text-[#cc9966]" : "text-[#d4d4d4] group-hover:text-[#a3a3a3] transition-colors")} />
                                {!isCollapsed && <span className="text-sm">{item.label}</span>}
                            </Link>
                        )
                    })}
                </nav>

                <div className="p-6 border-t border-[#e5e5e5]">
                    <div className={clsx(
                        "flex items-center gap-4 p-3 rounded-2xl hover:bg-[#f5f5f5] cursor-pointer text-[#737373] transition-colors",
                        isCollapsed && "justify-center"
                    )}>
                        <Settings size={22} className="text-[#d4d4d4]" />
                        {!isCollapsed && <span className="text-sm font-medium">Settings</span>}
                    </div>
                </div>
            </aside>

            {/* Mobile Nav */}
            <nav className="md:hidden fixed bottom-0 left-0 right-0 h-20 bg-white/90 backdrop-blur-xl border-t border-[#e5e5e5] flex items-center justify-around px-4 z-50">
                {NAV_ITEMS.slice(0, 4).map((item) => {
                    const isActive = pathname === item.path
                    return (
                        <Link 
                            key={item.path} 
                            href={item.path}
                            className={clsx(
                                "flex flex-col items-center justify-center p-3 rounded-2xl transition-all",
                                isActive ? "bg-[#cc9966]/10 text-[#cc9966]" : "text-[#a3a3a3] hover:bg-[#f5f5f5]"
                            )}
                        >
                            <item.icon size={22} />
                        </Link>
                    )
                })}
            </nav>
        </>
    )
}
