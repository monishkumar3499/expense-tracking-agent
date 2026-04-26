'use client'

import React, { useState, useEffect } from 'react'
import api, { CATEGORY_EMOJI } from '@/lib/api'
import { Search, ChevronLeft, ChevronRight, MoreHorizontal, Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { format } from 'date-fns'
import ConfirmModal from '@/components/ConfirmModal'

export default function TransactionsPage() {
    const [bills, setBills] = useState<any[]>([])
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [search, setSearch] = useState('')
    const [loading, setLoading] = useState(true)
    const [expandedBills, setExpandedBills] = useState<Set<string>>(new Set())
    const [confirmDelete, setConfirmDelete] = useState<{ isOpen: boolean, id: any }>({ isOpen: false, id: null })

    const fetchLedger = async () => {
        setLoading(true)
        try {
            const res = await api.get('/api/transactions', { 
                params: { page, limit: 12, search } 
            })
            setBills(res.data.bills || [])
            setTotal(res.data.total_pages * 12 || 0) // Using pages to approximate total for pagination
        } catch (err) {
            toast.error("Couldn't load ledger")
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        const timer = setTimeout(() => {
            fetchLedger()
        }, 300)
        return () => clearTimeout(timer)
    }, [page, search])

    const toggleBill = (id: string) => {
        const newExpanded = new Set(expandedBills)
        if (newExpanded.has(id)) newExpanded.delete(id)
        else newExpanded.add(id)
        setExpandedBills(newExpanded)
    }

    const handleDeleteBill = async (id: string) => {
        const loadingToast = toast.loading("Deleting bill...")
        try {
            await api.delete(`/api/transactions/bill/${id}`)
            toast.success("Bill deleted successfully", { id: loadingToast })
            setConfirmDelete({ isOpen: false, id: null })
            fetchLedger()
        } catch (err) {
            toast.error("Failed to delete bill", { id: loadingToast })
        }
    }

    return (
        <div className="p-8 md:p-12 w-full space-y-12 min-h-screen bg-white">
            <ConfirmModal 
                isOpen={confirmDelete.isOpen}
                title="Delete Entire Receipt?"
                message="This will remove all items associated with this bill. This action cannot be undone."
                confirmText="Delete Bill"
                variant="danger"
                onConfirm={() => handleDeleteBill(confirmDelete.id)}
                onCancel={() => setConfirmDelete({ isOpen: false, id: null })}
            />
            <header className="flex items-center justify-between">
                <div className="space-y-1">
                    <h1 className="text-4xl font-bold tracking-tight text-[#171717]">Ledger</h1>
                    <p className="text-[#a3a3a3] font-medium">Verified transaction history (Receipt-based view).</p>
                </div>
            </header>

            <div className="bg-white border border-[#e5e5e5] rounded-[2.5rem] shadow-sm overflow-hidden flex flex-col transition-all hover:shadow-xl duration-500">
                <div className="p-8 border-b border-[#e5e5e5] flex items-center justify-between bg-[#fcfcfc] gap-6">
                   <div className="relative flex-1 max-w-md">
                        <Search className="absolute left-4 top-1/2 -translate-y-1/2 text-[#d4d4d4]" size={18} />
                        <input 
                            value={search}
                            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                            placeholder="Search merchant, bill name or category..." 
                            className="w-full bg-white border border-[#e5e5e5] rounded-2xl pl-12 pr-4 py-3.5 text-sm outline-none focus:border-[#cc9966] transition-all shadow-sm"
                        />
                   </div>
                </div>

                <div className="overflow-auto flex-1">
                    <table className="w-full text-left border-separate border-spacing-0">
                        <thead>
                            <tr className="text-[#a3a3a3] text-[11px] uppercase font-bold tracking-[0.2em] border-b border-[#e5e5e5] bg-[#fcfcfc]/50">
                                <th className="p-6 px-10">Date</th>
                                <th className="p-6">Receipt Name / Merchant</th>
                                <th className="p-6">Type</th>
                                <th className="p-6 text-right px-10">Total Cost</th>
                                <th className="p-6"></th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[#e5e5e5]">
                            {loading && bills.length === 0 ? (
                                [1,2,3,4,5,6].map(i => <tr key={i} className="animate-pulse"><td colSpan={5} className="p-12"></td></tr>)
                            ) : bills.length === 0 ? (
                                <tr><td colSpan={5} className="p-20 text-center text-[#a3a3a3] font-bold">No transactions found</td></tr>
                            ) : bills.map(bill => (
                                <React.Fragment key={bill.id}>
                                    <tr 
                                        onClick={() => toggleBill(bill.id)}
                                        className="group hover:bg-[#fdf5eb]/50 transition-all cursor-pointer select-none active:bg-[#fdf5eb]"
                                    >
                                        <td className="p-6 px-10 text-sm text-[#a3a3a3] font-medium border-b border-[#f5f5f5]">
                                            {format(new Date(bill.date), 'dd MMM yyyy')}
                                        </td>
                                        <td className="p-6 border-b border-[#f5f5f5]">
                                            <div className="flex flex-col gap-1">
                                                <span className="text-[15px] font-bold text-[#171717]">{bill.name}</span>
                                                <span className="text-[10px] text-[#d4d4d4] font-bold uppercase tracking-wider">
                                                    {bill.items.length} item{bill.items.length > 1 ? 's' : ''}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="p-6 border-b border-[#f5f5f5]">
                                            <span className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-[11px] font-bold uppercase tracking-widest border ${bill.is_receipt ? 'bg-[#fdf5eb] text-[#cc9966] border-[#f4e2cc]' : 'bg-[#f5f5f5] text-[#737373] border-[#e5e5e5]'}`}>
                                                {bill.is_receipt ? 'Receipt' : 'Manual'}
                                            </span>
                                        </td>
                                        <td className="p-6 text-right border-b border-[#f5f5f5]">
                                            <div className="flex items-center justify-end gap-4">
                                                <span className="text-[17px] font-black text-[#171717]">₹{bill.total.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                                                <div className={`transition-transform duration-300 ${expandedBills.has(bill.id) ? 'rotate-180' : ''}`}>
                                                    <ChevronRight size={20} className="text-[#d4d4d4]" />
                                                </div>
                                            </div>
                                        </td>
                                        <td className="p-6 px-10 text-right border-b border-[#f5f5f5]">
                                            <button 
                                                onClick={(e) => { e.stopPropagation(); setConfirmDelete({ isOpen: true, id: bill.id }); }}
                                                className="p-2 text-[#d4d4d4] hover:text-[#ef4444] transition-all hover:bg-red-50 rounded-lg opacity-0 group-hover:opacity-100"
                                            >
                                                <Trash2 size={18} />
                                            </button>
                                        </td>
                                    </tr>
                                    
                                    {expandedBills.has(bill.id) && (
                                        <tr className="bg-[#fafafa]">
                                            <td colSpan={5} className="p-0 border-b border-[#e5e5e5]">
                                                <div className="p-8 px-10 space-y-6 animate-in slide-in-from-top-2 duration-300">
                                                    <div className="space-y-3">
                                                        {bill.items.map((item: any) => (
                                                            <div key={item.id} className="bg-white p-4 px-6 rounded-2xl border border-[#eeeeee] shadow-sm flex items-center justify-between hover:border-[#f4e2cc] transition-all group/item">
                                                                <div className="flex items-center gap-6 flex-1">
                                                                    <div className="w-10 h-10 rounded-xl bg-[#fdf5eb] flex items-center justify-center text-lg shrink-0">
                                                                        {CATEGORY_EMOJI[item.category] || '📦'}
                                                                    </div>
                                                                    <div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-8 flex-1">
                                                                        <p className="text-[14px] font-bold text-[#171717] min-w-[200px]">{item.description}</p>
                                                                        <p className="text-[10px] text-[#a3a3a3] font-bold uppercase tracking-widest bg-[#f5f5f5] px-3 py-1 rounded-full">{item.category}</p>
                                                                    </div>
                                                                </div>
                                                                <div className="flex items-center gap-6">
                                                                    <span className="text-[15px] font-black text-[#171717]">₹{item.amount.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                                                                    <button className="text-[#d4d4d4] hover:text-[#171717] transition-colors opacity-0 group-hover/item:opacity-100"><MoreHorizontal size={16} /></button>
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            </td>
                                        </tr>
                                    )}
                                </React.Fragment>
                            ))}
                        </tbody>
                    </table>
                </div>

                <div className="p-8 border-t border-[#e5e5e5] flex items-center justify-between bg-[#fcfcfc]">
                    <p className="text-sm text-[#a3a3a3] font-medium">
                        Page <span className="text-[#171717] font-bold">{page}</span>
                    </p>
                    <div className="flex gap-3">
                        <button disabled={page === 1} onClick={() => setPage(p => p - 1)} className="p-3 border border-[#e5e5e5] bg-white rounded-2xl hover:bg-[#f5f5f5] disabled:opacity-30 transition-all shadow-sm">
                            <ChevronLeft size={20} />
                        </button>
                        <button disabled={bills.length < 12} onClick={() => setPage(p => p + 1)} className="p-3 border border-[#e5e5e5] bg-white rounded-2xl hover:bg-[#f5f5f5] disabled:opacity-30 transition-all shadow-sm">
                            <ChevronRight size={20} />
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
