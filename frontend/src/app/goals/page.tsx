'use client'

import { useState, useEffect } from 'react'
import api from '@/lib/api'
import { Plus, Trophy, Edit2, Trash2, Calendar, Target as TargetIcon } from 'lucide-react'
import toast from 'react-hot-toast'
import { format, differenceInDays } from 'date-fns'

export default function GoalsPage() {
    const [goals, setGoals] = useState<any[]>([])
    const [loading, setLoading] = useState(true)

    const fetchGoals = async () => {
        setLoading(true)
        try {
            const res = await api.get('/api/analytics/goals')
            setGoals(res.data)
        } catch (err) {
            toast.error("Failed to load goals")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchGoals()
    }, [])

    return (
        <div className="p-8 md:p-12 w-full space-y-12 min-h-screen bg-white">
            <header className="flex items-center justify-between">
                <div>
                    <h1 className="text-4xl font-bold tracking-tight text-[#171717]">Savings Goals</h1>
                    <p className="text-[#a3a3a3] font-medium tracking-tight mt-1">Strategic financial milestones.</p>
                </div>
                <button className="flex items-center gap-2 px-6 py-3 bg-[#171717] text-white rounded-2xl text-sm font-bold shadow-xl shadow-black/10 hover:opacity-90 transition-all">
                    <Plus size={18} /> New Goal
                </button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
                {loading ? (
                    [1,2,3,4].map(i => <div key={i} className="h-96 bg-[#f5f5f5] rounded-[2.5rem] animate-pulse"></div>)
                ) : goals.length === 0 ? (
                    <div className="col-span-full py-32 bg-[#fafafa] border-2 border-dashed border-[#e5e5e5] rounded-[2.5rem] text-center">
                        <div className="w-20 h-20 bg-white border border-[#e5e5e5] rounded-3xl flex items-center justify-center mx-auto mb-6 text-[#d4d4d4] shadow-sm">
                            <Trophy size={32} />
                        </div>
                        <h3 className="text-xl font-bold text-[#171717]">No goals set yet</h3>
                        <p className="text-[#a3a3a3] text-sm mt-2 max-w-sm mx-auto font-medium">Define your future milestones to begin tracking your savings trajectory.</p>
                        <button className="mt-8 px-8 py-3 bg-white border border-[#e5e5e5] text-[#171717] rounded-xl font-bold hover:bg-[#f5f5f5] transition-all">Add First Goal</button>
                    </div>
                ) : goals.map(g => (
                    <div key={g.id} className="bg-white border border-[#e5e5e5] rounded-[2.5rem] p-10 flex flex-col items-center hover:shadow-2xl transition-all duration-500 group relative">
                        <div className="relative w-48 h-48 mb-10">
                            {/* SVG Ring Progress */}
                            <svg className="w-full h-full transform -rotate-90">
                                <circle
                                    cx="96" cy="96" r="80"
                                    stroke="currentColor"
                                    strokeWidth="10"
                                    fill="transparent"
                                    className="text-[#f5f5f5]"
                                />
                                <circle
                                    cx="96" cy="96" r="80"
                                    stroke="currentColor"
                                    strokeWidth="10"
                                    fill="transparent"
                                    strokeDasharray={502.6}
                                    strokeDashoffset={502.6 - (502.6 * (g.pct || 0))}
                                    strokeLinecap="round"
                                    className="text-[#cc9966] transition-all duration-1000 ease-out"
                                />
                            </svg>
                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                                <span className="text-3xl font-black text-[#171717]">{Math.round(g.pct * 100)}%</span>
                                <span className="text-[10px] text-[#a3a3a3] font-bold uppercase tracking-widest mt-1">Saved</span>
                            </div>
                        </div>

                        <div className="w-full text-center space-y-3 mb-10">
                            <h3 className="text-2xl font-bold text-[#171717]">{g.name}</h3>
                            <div className="flex items-center justify-center gap-6">
                                <div className="text-center">
                                    <p className="text-[10px] text-[#a3a3a3] uppercase tracking-widest font-black">Target</p>
                                    <p className="text-sm font-bold text-[#171717]">₹{g.target.toLocaleString()}</p>
                                </div>
                                <div className="w-px h-8 bg-[#e5e5e5]"></div>
                                <div className="text-center">
                                    <p className="text-[10px] text-[#a3a3a3] uppercase tracking-widest font-black">Current</p>
                                    <p className="text-sm font-bold text-[#10b981]">₹{g.current.toLocaleString()}</p>
                                </div>
                            </div>
                        </div>

                        {g.deadline && (
                            <div className="w-full bg-[#fdf5eb] rounded-2xl p-4 flex items-center justify-center gap-3 text-[#cc9966] text-xs font-bold mb-8">
                                <Calendar size={16} />
                                <span>{format(new Date(g.deadline), 'MMM dd, yyyy')}</span>
                                <span className="px-2 py-0.5 rounded-lg bg-white/50 text-[10px]">
                                    {differenceInDays(new Date(g.deadline), new Date())}D Left
                                </span>
                            </div>
                        )}

                        <div className="flex gap-4 mt-auto w-full opacity-0 group-hover:opacity-100 transition-all duration-300 transform translate-y-4 group-hover:translate-y-0">
                            <button className="flex-1 py-3 bg-[#171717] text-white rounded-xl text-xs font-bold hover:opacity-90 transition-all">
                                Update
                            </button>
                            <button className="p-3 border border-[#e5e5e5] rounded-xl text-[#d4d4d4] hover:text-[#ef4444] hover:border-[#ef4444] transition-all">
                                <Trash2 size={18} />
                            </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
