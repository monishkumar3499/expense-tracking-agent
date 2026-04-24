'use client'

import { useState, useEffect } from 'react'
import api, { CATEGORY_EMOJI } from '@/lib/api'
import { Search, Plus, ChevronLeft, ChevronRight, MoreHorizontal, Filter, Download } from 'lucide-react'
import toast from 'react-hot-toast'
import { format } from 'date-fns'

export default function TransactionsPage() {
    const [transactions, setTransactions] = useState<any[]>([])
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        const fetch = async () => {
            setLoading(true)
            try {
                const res = await api.get('/api/transactions', { params: { page, limit: 12 } })
                setTransactions(res.data.transactions)
                setTotal(res.data.total)
            } catch (err) {
                toast.error("Couldn't load ledger")
            } finally {
                setLoading(false)
            }
        }
        fetch()
    }, [page])

    return (
        <div className="p-8 md:p-12 w-full space-y-12 min-h-screen bg-white">
            <header className="flex items-center justify-between">
                <div className="space-y-1">
                    <h1 className="text-4xl font-bold tracking-tight text-[#171717]">Ledger</h1>
                    <p className="text-[#a3a3a3] font-medium">Verified transaction history.</p>
                </div>
                <div className="flex gap-3">
                    <button className="p-3 border border-[#e5e5e5] rounded-2xl hover:bg-[#f5f5f5] text-[#737373] transition-all">
                        <Download size={20} />
                    </button>
                    <button className="bg-[#171717] text-white px-8 py-3 rounded-2xl text-sm font-bold hover:opacity-90 transition-all flex items-center gap-2 shadow-xl shadow-black/10">
                        <Plus size={20} /> Add Transaction
                    </button>
                </div>
            </header>

            <div className="bg-white border border-[#e5e5e5] rounded-[2.5rem] shadow-sm overflow-hidden flex flex-col transition-all hover:shadow-xl duration-500">
                <div className="p-8 border-b border-[#e5e5e5] flex items-center justify-between bg-[#fcfcfc] gap-6">
                   <div className="relative flex-1 max-w-md">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[#d4d4d4]" size={18} />
                        <input 
                            placeholder="Search by merchant..." 
                            className="w-full bg-white border border-[#e5e5e5] rounded-2xl pl-12 pr-4 py-3.5 text-sm outline-none focus:border-[#cc9966] transition-all shadow-sm"
                        />
                   </div>
                   <button className="flex items-center gap-2 px-6 py-3.5 bg-white border border-[#e5e5e5] rounded-2xl text-xs font-bold text-[#737373] hover:text-[#171717] hover:bg-[#f5f5f5] transition-all shadow-sm">
                        <Filter size={16} /> Filters
                   </button>
                </div>

                <div className="overflow-auto flex-1">
                    <table className="w-full text-left border-collapse">
                        <thead>
                            <tr className="text-[#a3a3a3] text-[11px] uppercase font-bold tracking-[0.2em] border-b border-[#e5e5e5] bg-[#fcfcfc]/50">
                                <th className="p-6 px-10">Date</th>
                                <th className="p-6">Description</th>
                                <th className="p-6">Category</th>
                                <th className="p-6 text-right px-10">Amount</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[#e5e5e5]">
                            {loading ? (
                                [1,2,3,4,5,6].map(i => <tr key={i} className="animate-pulse"><td colSpan={4} className="p-12"></td></tr>)
                            ) : transactions.map(t => (
                                <tr key={t.id} className="group hover:bg-[#fdf5eb]/30 transition-colors">
                                    <td className="p-6 px-10 text-sm text-[#a3a3a3] font-medium">
                                        {format(new Date(t.date), 'dd MMM yyyy')}
                                    </td>
                                    <td className="p-6">
                                        <div className="flex flex-col gap-1">
                                            <span className="text-[15px] font-bold text-[#171717]">{t.merchant}</span>
                                            <span className="text-[10px] text-[#d4d4d4] font-bold uppercase tracking-wider">{t.source}</span>
                                        </div>
                                    </td>
                                    <td className="p-6">
                                        <span className="inline-flex items-center gap-2 px-4 py-2 bg-[#f5f5f5] text-[#525252] rounded-xl text-[13px] font-medium group-hover:bg-white transition-colors border border-transparent group-hover:border-[#e5e5e5]">
                                            <span className="text-lg">{CATEGORY_EMOJI[t.category] || '📦'}</span> {t.category}
                                        </span>
                                    </td>
                                    <td className="p-6 text-right px-10">
                                        <span className="text-[17px] font-black text-[#171717]">₹{t.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                <div className="p-8 border-t border-[#e5e5e5] flex items-center justify-between bg-[#fcfcfc]">
                    <p className="text-sm text-[#a3a3a3] font-medium">
                        Showing <span className="text-[#171717] font-bold">{(page-1)*12 + 1}</span> to <span className="text-[#171717] font-bold">{Math.min(page*12, total)}</span> of <span className="text-[#171717] font-bold">{total}</span>
                    </p>
                    <div className="flex gap-3">
                        <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="p-3 border border-[#e5e5e5] bg-white rounded-2xl hover:bg-[#f5f5f5] disabled:opacity-30 transition-all shadow-sm">
                            <ChevronLeft size={20} />
                        </button>
                        <button disabled={page >= Math.ceil(total/12)} onClick={() => setPage(p => p + 1)} className="p-3 border border-[#e5e5e5] bg-white rounded-2xl hover:bg-[#f5f5f5] disabled:opacity-30 transition-all shadow-sm">
                            <ChevronRight size={20} />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
