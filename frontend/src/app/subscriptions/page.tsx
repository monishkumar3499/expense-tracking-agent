'use client'

import { useState, useEffect } from 'react'
import api from '@/lib/api'
import { RefreshCw, Search, Calendar, ChevronRight, CreditCard, Sparkles } from 'lucide-react'
import toast from 'react-hot-toast'
import { format } from 'date-fns'
import StatusBadge from '@/components/StatusBadge'

export default function SubscriptionsPage() {
    const [subs, setSubs] = useState<any[]>([])
    const [loading, setLoading] = useState(true)
    const [isDetecting, setIsDetecting] = useState(false)

    const [isModalOpen, setIsModalOpen] = useState(false)
    const [newSub, setNewSub] = useState({
        merchant: '',
        avg_amount: '',
        category: 'Miscellaneous',
        frequency: 'monthly'
    })

    const fetchSubs = async () => {
        setLoading(true)
        try {
            const res = await api.get('/api/subscriptions')
            setSubs(res.data)
        } catch (err) {
            toast.error("Failed to load subscriptions")
        } finally {
            setLoading(false)
        }
    }

    const handleAddSub = async (e: React.FormEvent) => {
        e.preventDefault()
        try {
            await api.post('/api/subscriptions', {
                ...newSub,
                avg_amount: parseFloat(newSub.avg_amount)
            })
            toast.success("Recurring cost added")
            setIsModalOpen(false)
            setNewSub({ merchant: '', avg_amount: '', category: 'Miscellaneous', frequency: 'monthly' })
            fetchSubs()
        } catch (err) {
            toast.error("Failed to add recurring cost")
        }
    }

    const detectSubs = async () => {
        setIsDetecting(true)
        const load = toast.loading("Analyzing transaction patterns...")
        try {
            const res = await api.post('/api/subscriptions/detect')
            toast.success(`Found ${res.data.new} new recurring expenses!`, { id: load })
            fetchSubs()
        } catch (err) {
            toast.error("Detection failed", { id: load })
        } finally {
            setIsDetecting(false)
        }
    }

    useEffect(() => {
        fetchSubs()
    }, [])

    const totalMonthly = subs.reduce((acc, s) => {
        const amt = s.avg_amount
        if (s.frequency === 'yearly') return acc + (amt / 12)
        if (s.frequency === '6-months') return acc + (amt / 6)
        if (s.frequency === '3-months') return acc + (amt / 3)
        return acc + amt
    }, 0)

    return (
        <div className="p-8 md:p-12 w-full space-y-12 min-h-screen bg-white">
            <header className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                <div className="space-y-1">
                    <h1 className="text-4xl font-bold tracking-tight text-[#171717]">Recurring Costs</h1>
                    <p className="text-[#a3a3a3] font-medium tracking-tight mt-1">Automated financial commitments.</p>
                </div>
                <div className="flex items-center gap-6">
                    <StatusBadge />
                    <div className="flex gap-4">
                        <button 
                            onClick={detectSubs}
                            disabled={isDetecting}
                            className="flex items-center gap-2 px-6 py-3 border border-[#cc9966]/20 text-[#cc9966] bg-[#fdf5eb] rounded-2xl text-sm font-bold hover:bg-[#f4e2cc] transition-all disabled:opacity-50 shadow-sm"
                        >
                            <RefreshCw size={18} className={isDetecting ? 'animate-spin' : ''} /> Detect Patterns
                        </button>
                        <button 
                            onClick={() => setIsModalOpen(true)}
                            className="flex items-center gap-2 px-6 py-3 bg-[#171717] text-white rounded-2xl text-sm font-bold shadow-xl shadow-black/10 hover:opacity-90 transition-all"
                        >
                            New Fixed Cost
                        </button>
                    </div>
                </div>
            </header>

            {/* Modal */}
            {isModalOpen && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
                    <div className="bg-white rounded-[2.5rem] w-full max-w-lg p-10 shadow-2xl animate-in fade-in zoom-in duration-300">
                        <div className="flex justify-between items-center mb-8">
                            <h3 className="text-2xl font-bold text-[#171717]">Add Fixed Cost</h3>
                            <button onClick={() => setIsModalOpen(false)} className="text-[#a3a3a3] hover:text-[#171717]">✕</button>
                        </div>
                        <form onSubmit={handleAddSub} className="space-y-6">
                            <div className="space-y-2">
                                <label className="text-[10px] font-black uppercase tracking-widest text-[#a3a3a3]">Merchant / Service</label>
                                <input 
                                    required
                                    className="w-full bg-[#f5f5f5] border-none rounded-2xl p-4 text-sm font-medium outline-none focus:ring-2 focus:ring-[#cc9966]/20 transition-all"
                                    placeholder="e.g. Netflix, Rent, Gym"
                                    value={newSub.merchant}
                                    onChange={e => setNewSub({...newSub, merchant: e.target.value})}
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-6">
                                <div className="space-y-2">
                                    <label className="text-[10px] font-black uppercase tracking-widest text-[#a3a3a3]">Amount</label>
                                    <input 
                                        required
                                        type="number"
                                        className="w-full bg-[#f5f5f5] border-none rounded-2xl p-4 text-sm font-medium outline-none"
                                        placeholder="0.00"
                                        value={newSub.avg_amount}
                                        onChange={e => setNewSub({...newSub, avg_amount: e.target.value})}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <label className="text-[10px] font-black uppercase tracking-widest text-[#a3a3a3]">Interval</label>
                                    <div className="relative">
                                        <select 
                                            className="w-full appearance-none bg-[#f5f5f5] border-none rounded-2xl p-4 pr-10 text-sm font-medium outline-none cursor-pointer"
                                            value={newSub.frequency}
                                            onChange={e => setNewSub({...newSub, frequency: e.target.value})}
                                        >
                                            <option value="monthly">Monthly</option>
                                            <option value="yearly">Yearly</option>
                                            <option value="6-months">6 Months</option>
                                            <option value="3-months">Quarterly</option>
                                        </select>
                                        <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-[#a3a3a3]">
                                            <ChevronRight size={14} className="rotate-90" />
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <div className="space-y-2">
                                <label className="text-[10px] font-black uppercase tracking-widest text-[#a3a3a3]">Category</label>
                                <div className="relative">
                                    <select 
                                        className="w-full appearance-none bg-[#f5f5f5] border-none rounded-2xl p-4 pr-10 text-sm font-medium outline-none cursor-pointer"
                                        value={newSub.category}
                                        onChange={e => setNewSub({...newSub, category: e.target.value})}
                                    >
                                        <option>Food</option>
                                        <option>Transport</option>
                                        <option>Utilities</option>
                                        <option>Shopping</option>
                                        <option>Entertainment</option>
                                        <option>Healthcare</option>
                                        <option>Education</option>
                                        <option>Miscellaneous</option>
                                    </select>
                                    <div className="absolute right-4 top-1/2 -translate-y-1/2 pointer-events-none text-[#a3a3a3]">
                                        <ChevronRight size={14} className="rotate-90" />
                                    </div>
                                </div>
                            </div>
                            <button type="submit" className="w-full py-4 bg-[#cc9966] text-white rounded-2xl font-bold hover:shadow-lg hover:shadow-[#cc9966]/20 transition-all mt-4">
                                Save Commitment
                            </button>
                        </form>
                    </div>
                </div>
            )}

            {/* Summary Banner */}
            <div className="bg-white border border-[#e5e5e5] rounded-[2.5rem] p-10 flex flex-col md:flex-row justify-between items-center gap-12 relative overflow-hidden shadow-sm">
                <div className="absolute -top-24 -right-24 w-80 h-80 bg-[#fdf5eb] blur-[100px] rounded-full pointer-events-none"></div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-12 w-full md:w-auto flex-1 z-10">
                    <div className="space-y-1">
                        <p className="text-[10px] text-[#a3a3a3] uppercase tracking-[0.2em] font-black">Detected</p>
                        <p className="text-3xl font-black text-[#171717]">{subs.length} Active</p>
                    </div>
                    <div className="space-y-1">
                        <p className="text-[10px] text-[#a3a3a3] uppercase tracking-[0.2em] font-black">Monthly Burn</p>
                        <p className="text-3xl font-black text-[#ef4444]">₹{totalMonthly.toLocaleString()}</p>
                    </div>
                    <div className="space-y-1">
                        <p className="text-[10px] text-[#a3a3a3] uppercase tracking-[0.2em] font-black">Annual Total</p>
                        <p className="text-3xl font-black text-[#171717]">₹{(totalMonthly * 12).toLocaleString()}</p>
                    </div>
                </div>
                <div className="p-6 bg-[#fdf5eb] border border-[#f4e2cc] rounded-[2rem] text-xs text-[#cc9966] font-bold max-w-sm flex gap-4 items-center z-10 shadow-sm">
                    <div className="w-10 h-10 rounded-full bg-white flex items-center justify-center shrink-0 shadow-sm">
                         <Sparkles size={18} />
                    </div>
                    <p className="leading-relaxed">
                        Finn identified these patterns automatically. You could save <span className="text-[#171717]">₹{Math.round(totalMonthly * 0.15).toLocaleString()}</span> monthly by optimizing low-usage services.
                    </p>
                </div>
            </div>

            {/* Subscription Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 pb-32">
                {loading ? (
                    [1,2,3,4].map(i => <div key={i} className="h-64 bg-[#f5f5f5] rounded-[2rem] border border-[#e5e5e5] animate-pulse"></div>)
                ) : subs.length === 0 ? (
                    <div className="col-span-full py-32 text-center bg-[#fafafa] border-2 border-dashed border-[#e5e5e5] rounded-[2.5rem]">
                        <div className="w-20 h-20 bg-white border border-[#e5e5e5] rounded-3xl flex items-center justify-center mx-auto mb-6 text-[#d4d4d4] shadow-sm">
                            <CreditCard size={32} />
                        </div>
                        <h3 className="text-xl font-bold text-[#171717]">No recurring costs found</h3>
                        <p className="text-[#a3a3a3] text-sm mt-2 max-w-sm mx-auto font-medium">Try "Detect Patterns" to have Finn scan your transactions for automated billing cycles.</p>
                    </div>
                ) : subs.map(s => (
                    <div key={s.id} className="bg-white border border-[#e5e5e5] rounded-[2rem] p-8 hover:shadow-2xl transition-all duration-500 group cursor-pointer flex flex-col">
                        <div className="flex justify-between items-start mb-10">
                            <div className="flex items-center gap-4">
                                <div className="w-14 h-14 rounded-2xl bg-[#fdf5eb] flex items-center justify-center text-2xl shadow-sm border border-[#f4e2cc]">
                                    {s.category === 'Entertainment' ? '🎬' : s.category === 'Shopping' ? '📦' : '🔁'}
                                </div>
                                <div className="space-y-1">
                                    <h3 className="font-bold text-[#171717]">{s.merchant}</h3>
                                    <p className="text-[10px] text-[#a3a3a3] font-bold uppercase tracking-widest">{s.category}</p>
                                </div>
                            </div>
                        </div>

                        <div className="mb-10">
                            <p className="text-3xl font-black text-[#171717]">₹{s.avg_amount.toLocaleString()}<span className="text-xs text-[#a3a3a3] font-medium ml-2">/ {s.frequency}</span></p>
                        </div>

                        <div className="mt-auto flex items-center justify-between pt-6 border-t border-[#f5f5f5]">
                            <div className="flex items-center gap-3 text-xs text-[#a3a3a3] font-bold">
                                <Calendar size={16} className="text-[#d4d4d4]" />
                                Next: {format(new Date(s.next_expected), 'MMM dd')}
                            </div>
                            <div className="w-10 h-10 rounded-full bg-[#f5f5f5] flex items-center justify-center text-[#d4d4d4] group-hover:bg-[#cc9966] group-hover:text-white transition-all transform group-hover:scale-110">
                                <ChevronRight size={18} />
                            </div>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    )
}
