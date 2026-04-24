'use client'

import { useState, useEffect } from 'react'
import api from '@/lib/api'
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart as RePieChart, Pie, Cell
} from 'recharts'
import { Wallet, ShoppingCart, Target, AlertTriangle, ArrowUpRight, TrendingUp, PieChart as PieChartIcon } from 'lucide-react'
import clsx from 'clsx'
import StatusBadge from '@/components/StatusBadge'

const COLORS = ['#cc9966', '#a3a3a3', '#d4d4d4', '#e5e5e5', '#f5f5f5']

export default function Dashboard() {
    const [summary, setSummary] = useState<any>(null)
    const [lastMonthSummary, setLastMonthSummary] = useState<any>(null)
    const [todaySummary, setTodaySummary] = useState<any>(null)
    const [trend, setTrend] = useState<any[]>([])
    const [forecast, setForecast] = useState<any>(null)
    const [budgets, setBudgets] = useState<any[]>([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [s, sl, st, t, f, b] = await Promise.all([
                    api.get('/api/analytics/summary', { params: { period: 'this_month' } }),
                    api.get('/api/analytics/summary', { params: { period: 'last_month' } }),
                    api.get('/api/analytics/summary', { params: { period: 'today' } }),
                    api.get('/api/analytics/trend'),
                    api.get('/api/analytics/forecast'),
                    api.get('/api/analytics/budgets'),
                ])
                setSummary(s.data)
                setLastMonthSummary(sl.data)
                setTodaySummary(st.data)
                setTrend(t.data)
                setForecast(f.data)
                setBudgets(b.data)
            } catch (err) {
                console.error("Failed to fetch dashboard data")
            } finally {
                setLoading(false)
            }
        }
        fetchData()
    }, [])

    if (loading) return <div className="p-12 animate-pulse space-y-12"><div className="h-48 bg-[#f5f5f5] rounded-[2rem] w-full"></div><div className="grid grid-cols-2 gap-12"><div className="h-96 bg-[#f5f5f5] rounded-[2rem]"></div><div className="h-96 bg-[#f5f5f5] rounded-[2rem]"></div></div></div>

    const spendingTrend = (() => {
        if (!summary || !lastMonthSummary || lastMonthSummary.total === 0) return "Starting point"
        const diff = ((summary.total - lastMonthSummary.total) / lastMonthSummary.total) * 100
        return `${diff > 0 ? '+' : ''}${diff.toFixed(1)}% vs last month`
    })()

    const todayTrend = todaySummary?.transaction_count > 0 
        ? `${todaySummary.transaction_count} new today` 
        : "No activity today"

    const pieData = summary ? Object.entries(summary.by_category).map(([name, value]) => ({ name, value })) : []

    return (
        <div className="p-8 md:p-12 w-full space-y-12 pb-32 min-h-screen bg-white">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-2">
                    <h1 className="text-4xl font-bold tracking-tight text-[#171717]">Overview</h1>
                    <p className="text-[#a3a3a3] font-medium">Real-time financial intelligence.</p>
                </div>
                <div className="flex items-center gap-3 px-4 py-2 bg-[#fdf5eb] rounded-full border border-[#f4e2cc]">
                    <div className="w-2 h-2 rounded-full bg-[#10b981] animate-pulse"></div>
                    <span className="text-xs font-bold uppercase tracking-wider text-[#cc9966]">Live Feed</span>
                </div>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                <KpiCard title="Total Spending" value={`₹${summary?.total.toLocaleString()}`} icon={Wallet} trend={spendingTrend} />
                <KpiCard title="Total Entries" value={summary?.transaction_count} icon={ShoppingCart} trend={todayTrend} />
                <KpiCard 
                    title="Projected Bills" 
                    value={`₹${forecast?.recurring_outflow?.toLocaleString() ?? '0'}`} 
                    icon={AlertTriangle} 
                    trend={`Next ${forecast?.forecast_days || 30} days`} 
                />
                <KpiCard 
                    title="Budget Health" 
                    value={budgets.length > 0 ? `${Math.round((budgets.filter(b => !b.over_budget).length / budgets.length) * 100)}%` : 'Active'} 
                    icon={Target} 
                    trend={budgets.length > 0 ? `${budgets.filter(b => b.over_budget).length} filters hit` : "No limits set"} 
                />
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
                <div className="bg-white border border-[#e5e5e5] rounded-[2.5rem] p-8 shadow-sm hover:shadow-xl transition-all duration-500">
                    <div className="flex items-center justify-between mb-8">
                        <h3 className="text-lg font-bold text-[#171717]">Spending Trajectory</h3>
                        <div className="relative">
                            <select className="appearance-none bg-[#f5f5f5] border-none rounded-xl px-5 py-2.5 pr-10 text-[10px] font-bold outline-none text-[#171717] hover:bg-[#ebebeb] transition-all cursor-pointer">
                                <option>Last 6 Months</option>
                                <option>Last Year</option>
                            </select>
                            <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-[#a3a3a3]">
                                <ArrowUpRight size={14} className="rotate-45" />
                            </div>
                        </div>
                    </div>
                    <div className="h-72">
                        {trend.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-[#d4d4d4] gap-3 border-2 border-dashed border-[#f5f5f5] rounded-3xl">
                                <TrendingUp size={40} strokeWidth={1.5} className="opacity-40" />
                                <p className="text-xs font-bold uppercase tracking-widest text-[#a3a3a3]">No data available</p>
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={trend}>
                                    <defs>
                                        <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#cc9966" stopOpacity={0.15} />
                                            <stop offset="95%" stopColor="#cc9966" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f5f5f5" vertical={false} />
                                    <XAxis dataKey="month" stroke="#a3a3a3" fontSize={11} tickLine={false} axisLine={false} dy={10} />
                                    <YAxis stroke="#a3a3a3" fontSize={11} tickLine={false} axisLine={false} tickFormatter={(val) => `₹${val / 1000}k`} dx={-10} />
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e5e5e5', borderRadius: '16px', boxShadow: '0 10px 25px rgba(0,0,0,0.05)' }}
                                        itemStyle={{ fontSize: '12px', fontWeight: 'bold' }}
                                    />
                                    <Area type="monotone" dataKey="total" stroke="#cc9966" strokeWidth={3} fillOpacity={1} fill="url(#colorTotal)" />
                                </AreaChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>

                <div className="bg-white border border-[#e5e5e5] rounded-[2.5rem] p-8 shadow-sm hover:shadow-xl transition-all duration-500 flex flex-col items-center justify-center">
                    <h3 className="text-lg font-bold mb-8 w-full text-left">Category Distribution</h3>
                    <div className="h-64 w-full">
                        {pieData.length === 0 ? (
                            <div className="h-full flex flex-col items-center justify-center text-[#d4d4d4] gap-3 border-2 border-dashed border-[#f5f5f5] rounded-3xl">
                                <PieChartIcon size={40} strokeWidth={1.5} className="opacity-40" />
                                <p className="text-xs font-bold uppercase tracking-widest text-[#a3a3a3]">No data available</p>
                            </div>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <RePieChart>
                                    <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={10} dataKey="value">
                                        {pieData.map((e, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} strokeWidth={0} />)}
                                    </Pie>
                                    <Tooltip
                                        contentStyle={{ backgroundColor: '#ffffff', border: '1px solid #e5e5e5', borderRadius: '16px', boxShadow: '0 10px 25px rgba(0,0,0,0.05)' }}
                                    />
                                </RePieChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                    <div className="mt-8 grid grid-cols-2 gap-4 w-full">
                        {pieData.slice(0, 6).map((d, i) => (
                            <div key={i} className="flex items-center gap-2">
                                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }}></div>
                                <span className="text-[10px] font-bold uppercase tracking-wider text-[#a3a3a3] truncate">{d.name}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    )
}

function KpiCard({ title, value, icon: Icon, trend }: any) {
    return (
        <div className="claude-card group">
            <div className="flex justify-between items-start mb-6">
                <div className="w-12 h-12 bg-[#fdf5eb] rounded-2xl flex items-center justify-center text-[#cc9966] transition-transform group-hover:scale-110 duration-300">
                    <Icon size={24} />
                </div>
                <div className="text-[10px] font-bold text-[#10b981] bg-[#10b981]/10 px-2 py-1 rounded-lg">
                    {trend}
                </div>
            </div>
            <p className="text-xs font-bold uppercase tracking-widest text-[#a3a3a3] mb-2">{title}</p>
            <h4 className="text-3xl font-bold text-[#171717]">{value}</h4>
        </div>
    )
}
