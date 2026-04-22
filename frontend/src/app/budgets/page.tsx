'use client'

import { useState, useEffect } from 'react'
import api, { CATEGORIES, CATEGORY_EMOJI } from '@/lib/api'
import { Plus, Target, Edit2, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import clsx from 'clsx'

export default function BudgetsPage() {
    const [budgets, setBudgets] = useState<any[]>([])
    const [loading, setLoading] = useState(true)

    const fetchBudgets = async () => {
        setLoading(true)
        try {
            const res = await api.get('/api/analytics/budgets')
            setBudgets(res.data)
        } catch (err) {
            toast.error("Failed to load budgets")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchBudgets()
    }, [])

    const deleteBudget = async (id: string | any, category?: string) => {
        if (!confirm(`Delete budget for ${category}?`)) return
        try {
            if (id) {
                await api.delete(`/api/budgets/${id}`)
                toast.success("Budget deleted")
                fetchBudgets()
            }
        } catch (err) {
            toast.error("Failed to delete")
        }
    }

    return (
        <div className="p-8 md:p-12 w-full space-y-12 min-h-screen bg-white">
            <header className="flex items-center justify-between">
                <div>
                    <h1 className="text-4xl font-bold tracking-tight text-[#171717]">Budgets</h1>
                    <p className="text-[#a3a3a3] font-medium tracking-tight mt-1">{new Date().toLocaleString('en-us', { month: 'long', year: 'numeric' })} Control</p>
                </div>
                <button className="flex items-center gap-2 px-6 py-3 bg-[#cc9966] text-white rounded-2xl text-sm font-bold shadow-xl shadow-[#cc9966]/20 hover:opacity-90 transition-all">
                    <Plus size={18} /> Add Budget
                </button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-8">
                {loading ? (
                    [1,2,3,4].map(i => <div key={i} className="h-64 bg-[#f5f5f5] rounded-[2rem] border border-[#e5e5e5] animate-pulse"></div>)
                ) : budgets.length === 0 ? (
                    <div className="col-span-full py-32 bg-[#fafafa] border-2 border-dashed border-[#e5e5e5] rounded-[2.5rem] text-center">
                        <div className="w-20 h-20 bg-white border border-[#e5e5e5] rounded-3xl flex items-center justify-center mx-auto mb-6 text-[#d4d4d4] shadow-sm">
                            <Target size={32} />
                        </div>
                        <h3 className="text-xl font-bold text-[#171717]">No active budgets</h3>
                        <p className="text-[#a3a3a3] text-sm mt-2 max-w-sm mx-auto font-medium">Define limits for your spending categories to receive real-time alerts from Finn.</p>
                        <button className="mt-8 px-8 py-3 bg-white border border-[#e5e5e5] text-[#171717] rounded-xl font-bold hover:bg-[#f5f5f5] transition-all shadow-sm">Create First Budget</button>
                    </div>
                ) : budgets.map(b => (
                    <div key={b.category} className="bg-white border border-[#e5e5e5] rounded-[2rem] p-8 shadow-sm hover:shadow-xl transition-all duration-500 relative overflow-hidden group">
                        <div className={clsx(
                            "absolute top-0 left-0 right-0 h-1.5",
                            b.over_budget ? "bg-[#ef4444]" : b.alert ? "bg-[#f59e0b]" : "bg-[#10b981]"
                        )}></div>
                        
                        <div className="flex justify-between items-start mb-8">
                            <div className="flex items-center gap-4">
                                <div className="w-12 h-12 bg-[#fdf5eb] rounded-2xl flex items-center justify-center text-2xl">
                                    {CATEGORY_EMOJI[b.category] || '📦'}
                                </div>
                                <div className="space-y-1">
                                    <h3 className="font-bold text-[#171717]">{b.category}</h3>
                                    <div className={clsx(
                                        "text-[10px] font-bold px-2 py-0.5 rounded-lg uppercase tracking-wider inline-block",
                                        b.over_budget ? "bg-[#ef4444]/10 text-[#ef4444]" : b.alert ? "bg-[#f59e0b]/10 text-[#f59e0b]" : "bg-[#10b981]/10 text-[#10b981]"
                                    )}>
                                        {b.over_budget ? 'Over Limit' : b.alert ? 'Warning' : 'Healthy'}
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="space-y-6">
                            <div className="flex justify-between items-end">
                                <div>
                                    <p className="text-[10px] text-[#a3a3a3] uppercase tracking-widest font-black">Spent</p>
                                    <p className="text-2xl font-black text-[#171717]">₹{b.spent.toLocaleString()}</p>
                                </div>
                                <div className="text-right">
                                    <p className="text-[10px] text-[#a3a3a3] uppercase tracking-widest font-black">of</p>
                                    <p className="text-sm font-bold text-[#737373]">₹{b.limit.toLocaleString()}</p>
                                </div>
                            </div>

                            <div className="space-y-3">
                                <div className="h-2.5 w-full bg-[#f5f5f5] rounded-full overflow-hidden">
                                    <div 
                                        className={clsx(
                                            "h-full rounded-full transition-all duration-1000",
                                            b.over_budget ? "bg-[#ef4444]" : b.alert ? "bg-[#f59e0b]" : "bg-[#cc9966]"
                                        )}
                                        style={{ width: `${Math.min(b.utilisation_pct * 100, 100)}%` }}
                                    ></div>
                                </div>
                                <div className="flex justify-between text-[11px] font-bold">
                                    <span className={clsx(b.over_budget ? "text-[#ef4444]" : b.alert ? "text-[#f59e0b]" : "text-[#cc9966]")}>
                                        {Math.round(b.utilisation_pct * 100)}% Utilized
                                    </span>
                                    <span className="text-[#a3a3a3]">₹{b.remaining.toLocaleString()} balance</span>
                                </div>
                            </div>
                        </div>

                        <div className="mt-8 pt-6 border-t border-[#f5f5f5] flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-all duration-300 transform translate-y-2 group-hover:translate-y-0">
                             <button className="p-2.5 bg-white border border-[#e5e5e5] rounded-xl text-[#a3a3a3] hover:text-[#cc9966] hover:border-[#cc9966] transition-all">
                                <Edit2 size={16} />
                             </button>
                             <button onClick={() => deleteBudget(b.id, b.category)} className="p-2.5 bg-white border border-[#e5e5e5] rounded-xl text-[#a3a3a3] hover:text-[#ef4444] hover:border-[#ef4444] transition-all">
                                <Trash2 size={16} />
                             </button>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
