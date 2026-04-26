'use client'

import { useState, useEffect } from 'react'
import api from '@/lib/api'
import { Plus, Trophy, Edit2, Trash2, Calendar, Target as TargetIcon } from 'lucide-react'
import toast from 'react-hot-toast'
import { format, differenceInDays } from 'date-fns'
import ConfirmModal from '@/components/ConfirmModal'

const CATEGORIES = ['Food', 'Transport', 'Utilities', 'Entertainment', 'Shopping', 'Health', 'Travel', 'Miscellaneous']

export default function GoalsPage() {
    const [financialGoals, setFinancialGoals] = useState<any[]>([])
    const [loading, setLoading] = useState(true)
    const [showFinModal, setShowFinModal] = useState(false)
    const [editingGoalId, setEditingGoalId] = useState<number | null>(null)

    // Confirm Modal State
    const [confirmDelete, setConfirmDelete] = useState<{ isOpen: boolean, id: any }>({ isOpen: false, id: null })

    // Form State for New Financial Goal
    const [newFinGoal, setNewFinGoal] = useState({
        timeline: '1_month',
        total_budget: '' as any,
        category_budgets: {} as Record<string, number>,
        start_date: format(new Date(), 'yyyy-MM-dd'),
        end_date: format(new Date(new Date().setMonth(new Date().getMonth() + 1)), 'yyyy-MM-dd')
    })
    const [newCat, setNewCat] = useState({ name: CATEGORIES[0], amount: '' as any })

    const fetchAllData = async () => {
        setLoading(true)
        try {
            const res = await api.get('/api/financial-goals')
            // Filter out deleted ones just in case backend doesn't
            setFinancialGoals(res.data.filter((g: any) => g.status !== 'deleted'))
        } catch (err) {
            console.error("Failed to load financial goals")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchAllData()
    }, [])

    const handleCreateFinGoal = async () => {
        if (Number(newFinGoal.total_budget) <= 0) {
            toast.error("Please enter a valid amount")
            return
        }
        try {
            if (editingGoalId) {
                await api.put(`/api/financial-goals/${editingGoalId}`, {
                    ...newFinGoal,
                    total_budget: Number(newFinGoal.total_budget)
                })
                toast.success("Goal updated!")
            } else {
                await api.post('/api/financial-goals', {
                    ...newFinGoal,
                    total_budget: Number(newFinGoal.total_budget)
                })
                toast.success("Budget Goal set!")
            }
            
            setShowFinModal(false)
            setEditingGoalId(null)
            fetchAllData()
            setNewFinGoal({
                timeline: '1_month',
                total_budget: '',
                category_budgets: {},
                start_date: format(new Date(), 'yyyy-MM-dd'),
                end_date: format(new Date(new Date().setMonth(new Date().getMonth() + 1)), 'yyyy-MM-dd')
            })
        } catch (err) {
            toast.error("Operation failed")
        }
    }

    const handleEditClick = (g: any, e: React.MouseEvent) => {
        e.stopPropagation()
        setEditingGoalId(g.id)
        setNewFinGoal({
            timeline: g.timeline,
            total_budget: g.total_budget,
            category_budgets: g.category_budgets,
            start_date: g.start_date,
            end_date: g.end_date
        })
        setShowFinModal(true)
    }

    const handleDeleteFinGoal = async (id: any) => {
        const loadingToast = toast.loading("Removing goal...")
        try {
            await api.delete(`/api/financial-goals/${id}`)
            toast.success("Goal removed", { id: loadingToast })
            setConfirmDelete({ isOpen: false, id: null })
            fetchAllData()
        } catch (err) {
            toast.error("Delete failed", { id: loadingToast })
        }
    }

    return (
        <div className="p-8 md:p-12 w-full space-y-12 min-h-screen bg-white">
            <ConfirmModal 
                isOpen={confirmDelete.isOpen}
                title="Remove Budget Goal?"
                message="This will stop tracking your spending health for this period. You can always set a new one later."
                confirmText="Remove Goal"
                variant="danger"
                onConfirm={() => handleDeleteFinGoal(confirmDelete.id)}
                onCancel={() => setConfirmDelete({ isOpen: false, id: null })}
            />
            
            <header className="flex items-center justify-between">
                <div>
                    <h1 className="text-4xl font-bold tracking-tight text-[#171717]">Budgets & Goals</h1>
                    <p className="text-[#a3a3a3] font-medium tracking-tight mt-1">Real-time tracking of your spending limits across timelines.</p>
                </div>
                <button 
                    onClick={() => {
                        setEditingGoalId(null)
                        setNewFinGoal({
                            timeline: '1_month',
                            total_budget: '',
                            category_budgets: {},
                            start_date: format(new Date(), 'yyyy-MM-dd'),
                            end_date: format(new Date(new Date().setMonth(new Date().getMonth() + 1)), 'yyyy-MM-dd')
                        })
                        setShowFinModal(true)
                    }}
                    className="flex items-center gap-2 px-6 py-3 bg-[#171717] text-white rounded-2xl text-sm font-bold shadow-xl shadow-black/10 hover:opacity-90 transition-all"
                >
                    <TargetIcon size={18} /> Set Budget Goal
                </button>
            </header>

            <div className="space-y-6">
                {loading ? (
                    [1,2].map(i => <div key={i} className="h-32 bg-[#f5f5f5] rounded-3xl animate-pulse"></div>)
                ) : financialGoals.length === 0 ? (
                    <div className="py-20 bg-[#fafafa] border-2 border-dashed border-[#e5e5e5] rounded-[2.5rem] text-center">
                        <h3 className="text-xl font-bold text-[#171717]">No financial goals active</h3>
                        <p className="text-[#a3a3a3] text-sm mt-2">Set a monthly, 6-month, or yearly budget to track your spending health.</p>
                    </div>
                ) : financialGoals.map(g => (
                    <div 
                        key={g.id} 
                        className="w-full bg-white border border-[#e5e5e5] rounded-3xl p-8 hover:shadow-lg transition-all relative overflow-hidden group"
                    >
                        <div 
                            className="absolute bottom-0 left-0 h-1 bg-[#10b981] transition-all duration-1000"
                            style={{ width: `${g.health_score}%` }}
                        />

                        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                            <div className="flex items-center gap-6">
                                <div className="px-4 py-1.5 bg-[#f5f5f5] text-[#171717] rounded-full text-[10px] font-black uppercase tracking-widest border border-[#e5e5e5]">
                                    {g.timeline.replace('_', ' ')}
                                </div>
                                <div>
                                    <h3 className="text-xl font-bold text-[#171717]">Budget: ₹{g.total_budget.toLocaleString()}</h3>
                                    <p className="text-xs text-[#a3a3a3] font-medium">
                                        {format(new Date(g.start_date), 'MMM dd')} — {format(new Date(g.end_date), 'MMM dd, yyyy')}
                                    </p>
                                </div>
                            </div>

                            <div className="flex-1 max-w-md">
                                <div className="flex justify-between text-[10px] font-black uppercase tracking-widest mb-2">
                                    <span className="text-[#a3a3a3]">Spent: ₹{Math.round(g.total_spent).toLocaleString()}</span>
                                    <span className={g.progress_percentage > 100 ? 'text-[#ef4444]' : 'text-[#10b981]'}>
                                        {g.progress_percentage}% consumed
                                    </span>
                                </div>
                                <div className="h-2 bg-[#f5f5f5] rounded-full overflow-hidden">
                                    <div 
                                        className={`h-full transition-all duration-1000 ${g.progress_percentage > 100 ? 'bg-[#ef4444]' : 'bg-[#171717]'}`}
                                        style={{ width: `${Math.min(100, g.progress_percentage)}%` }}
                                    />
                                </div>
                            </div>

                            <div className="flex items-center gap-2">
                                <div className="text-right mr-4">
                                    <p className="text-[10px] text-[#a3a3a3] uppercase tracking-widest font-black">Health Score</p>
                                    <p className={`text-xl font-black ${g.health_score > 80 ? 'text-[#10b981]' : g.health_score > 50 ? 'text-[#f59e0b]' : 'text-[#ef4444]'}`}>
                                        {Math.round(g.health_score)}%
                                    </p>
                                </div>
                                <button 
                                    onClick={(e) => handleEditClick(g, e)}
                                    className="p-3 text-[#d4d4d4] hover:text-[#171717] transition-colors"
                                >
                                    <Edit2 size={18} />
                                </button>
                                <button 
                                    onClick={(e) => { e.stopPropagation(); setConfirmDelete({ isOpen: true, id: g.id }); }}
                                    className="p-3 text-[#d4d4d4] hover:text-[#ef4444] transition-colors"
                                >
                                    <Trash2 size={18} />
                                </button>
                            </div>
                        </div>

                        {/* Category Breakdown - Always Visible if categories exist */}
                        {g.category_progress && Object.keys(g.category_progress).length > 0 && (
                            <div className="mt-8 pt-8 border-t border-[#f5f5f5]">
                                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-x-12 gap-y-6">
                                    {Object.entries(g.category_progress).map(([cat, data]: [string, any]) => (
                                        <div key={cat} className="space-y-2">
                                            <div className="flex justify-between text-[10px] font-black uppercase tracking-widest">
                                                <span className="text-[#171717]">{cat}</span>
                                                <span className="text-[#a3a3a3]">₹{Math.round(data.spent).toLocaleString()} / ₹{data.budget.toLocaleString()}</span>
                                            </div>
                                            <div className="h-1 bg-[#f5f5f5] rounded-full overflow-hidden">
                                                <div 
                                                    className={`h-full transition-all duration-1000 ${data.percentage > 100 ? 'bg-[#ef4444]' : 'bg-[#cc9966]'}`}
                                                    style={{ width: `${Math.min(100, data.percentage)}%` }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ))}
            </div>

            {showFinModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-sm">
                    <div className="bg-white w-full max-w-2xl rounded-[2.5rem] p-10 shadow-2xl space-y-8">
                        <header>
                            <h3 className="text-3xl font-bold text-[#171717]">{editingGoalId ? 'Edit Financial Goal' : 'Set Financial Goal'}</h3>
                            <p className="text-[#a3a3a3] font-medium">Define your spending limits and categories.</p>
                        </header>

                        <div className="grid grid-cols-2 gap-6">
                            <div className="space-y-2">
                                <label className="text-[10px] font-black uppercase tracking-widest text-[#a3a3a3]">Timeline</label>
                                <select 
                                    className="w-full px-5 py-4 bg-[#f5f5f5] border-none rounded-2xl font-bold text-[#171717] outline-none"
                                    value={newFinGoal.timeline}
                                    onChange={(e) => {
                                        const tl = e.target.value;
                                        const end = new Date();
                                        if (tl === '6_months') end.setMonth(end.getMonth() + 6);
                                        else if (tl === '1_year') end.setFullYear(end.getFullYear() + 1);
                                        else end.setMonth(end.getMonth() + 1);
                                        setNewFinGoal({...newFinGoal, timeline: tl, end_date: format(end, 'yyyy-MM-dd')});
                                    }}
                                >
                                    <option value="1_month">1 Month</option>
                                    <option value="6_months">6 Months</option>
                                    <option value="1_year">1 Year</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label className="text-[10px] font-black uppercase tracking-widest text-[#a3a3a3]">Total Budget (₹)</label>
                                <input 
                                    type="number" 
                                    className="w-full px-5 py-4 bg-[#f5f5f5] border-none rounded-2xl font-bold text-[#171717] outline-none"
                                    placeholder="Enter amount"
                                    value={newFinGoal.total_budget}
                                    onChange={(e) => setNewFinGoal({...newFinGoal, total_budget: e.target.value})}
                                />
                            </div>
                        </div>

                        <div className="space-y-4">
                            <label className="text-[10px] font-black uppercase tracking-widest text-[#a3a3a3]">Category Budgets</label>
                            <div className="flex gap-4">
                                <select 
                                    className="flex-1 px-5 py-4 bg-[#f5f5f5] border-none rounded-2xl font-bold text-[#171717] outline-none"
                                    value={newCat.name}
                                    onChange={(e) => setNewCat({...newCat, name: e.target.value})}
                                >
                                    {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                                </select>
                                <input 
                                    type="number"
                                    placeholder="Amount"
                                    className="w-32 px-5 py-4 bg-[#f5f5f5] border-none rounded-2xl font-bold text-[#171717] outline-none"
                                    value={newCat.amount}
                                    onChange={(e) => setNewCat({...newCat, amount: e.target.value})}
                                />
                                <button 
                                    onClick={() => {
                                        if (Number(newCat.amount) <= 0) {
                                            toast.error("Invalid amount")
                                            return
                                        }
                                        setNewFinGoal({
                                            ...newFinGoal, 
                                            category_budgets: {...newFinGoal.category_budgets, [newCat.name]: Number(newCat.amount)}
                                        });
                                        setNewCat({ name: CATEGORIES[0], amount: '' });
                                    }}
                                    className="p-4 bg-[#171717] text-white rounded-2xl"
                                >
                                    <Plus size={24} />
                                </button>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {Object.entries(newFinGoal.category_budgets).map(([name, amt]) => (
                                    <div key={name} className="px-4 py-2 bg-[#f5f5f5] rounded-xl text-xs font-bold flex items-center gap-2">
                                        {name}: ₹{amt.toLocaleString()}
                                        <button 
                                            onClick={() => {
                                                const nb = {...newFinGoal.category_budgets};
                                                delete nb[name];
                                                setNewFinGoal({...newFinGoal, category_budgets: nb});
                                            }}
                                            className="text-[#ef4444]"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="flex gap-4 pt-4">
                            <button 
                                onClick={() => setShowFinModal(false)}
                                className="flex-1 py-4 border border-[#e5e5e5] rounded-2xl font-bold hover:bg-[#f5f5f5] transition-all"
                            >
                                Cancel
                            </button>
                            <button 
                                onClick={handleCreateFinGoal}
                                className="flex-1 py-4 bg-[#171717] text-white rounded-2xl font-bold shadow-xl shadow-black/10 hover:opacity-90 transition-all"
                            >
                                Create Goal
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
