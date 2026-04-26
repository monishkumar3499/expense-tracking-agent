'use client'

import { useState, useEffect } from 'react'
import { CATEGORIES } from '@/lib/api'
import { X, Trash2, Check } from 'lucide-react'
import api from '@/lib/api'
import toast from 'react-hot-toast'

interface Transaction {
    merchant: string
    amount: number
    date: string
    category: string
    description?: string
}

interface Props {
    isOpen: boolean
    onClose: () => void
    extractedData: {
        transactions: Transaction[]
        document_type: string
        file_id: string
        bill_name?: string
        bill_total?: number
    }
    onSaved: () => void
}

export default function UploadConfirmModal({ isOpen, onClose, extractedData, onSaved }: Props) {
    const [txns, setTxns] = useState<Transaction[]>(extractedData?.transactions || [])
    const [billName, setBillName] = useState(extractedData?.bill_name || '')

    useEffect(() => {
        if (extractedData?.transactions) setTxns(extractedData.transactions)
        if (extractedData?.bill_name) setBillName(extractedData.bill_name)
    }, [extractedData])

    if (!isOpen) return null

    const handleUpdate = (index: number, field: keyof Transaction, value: any) => {
        const newTxns = [...txns]
        newTxns[index] = { ...newTxns[index], [field]: value }
        setTxns(newTxns)
    }

    const handleSave = async () => {
        const loading = toast.loading('Syncing to ledger...')
        const finalTotal = txns.reduce((acc, t) => acc + t.amount, 0)
        try {
            await api.post('/api/upload/confirm', { 
                transactions: txns.map(t => ({ 
                    ...t, 
                    file_id: extractedData?.file_id, 
                    source: extractedData?.document_type,
                    bill_name: billName,
                    bill_total: finalTotal
                })) 
            })
            toast.success('Synced successfully', { id: loading })
            onSaved()
            onClose()
        } catch (err) {
            toast.error('Failed to sync', { id: loading })
        }
    }

    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="bg-[#171717] border border-[#262626] rounded-3xl w-full max-w-4xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
                <div className="p-8 border-b border-[#262626] flex items-center justify-between">
                    <div className="flex-1">
                        <h2 className="text-xl font-bold">Review Transactions</h2>
                        <input 
                            value={billName}
                            onChange={(e) => setBillName(e.target.value)}
                            placeholder="Receipt Name (e.g. Weekly Groceries)"
                            className="bg-transparent border-none text-[#cc9966] text-xs uppercase tracking-widest mt-1 font-bold w-full outline-none focus:ring-0 placeholder:text-[#404040]"
                        />
                    </div>
                    <button onClick={onClose} className="text-[#404040] hover:text-white transition-colors">
                        <X size={24} />
                    </button>
                </div>

                <div className="flex-1 overflow-auto p-8">
                    <table className="w-full text-left">
                        <thead>
                            <tr className="text-[#404040] text-[10px] uppercase tracking-[0.2em] font-bold border-b border-[#262626]">
                                <th className="pb-4 px-2">Merchant</th>
                                <th className="pb-4 px-2">Amount</th>
                                <th className="pb-4 px-2">Date</th>
                                <th className="pb-4 px-2">Category</th>
                                <th className="pb-4"></th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-[#262626]">
                            {txns.map((txn, idx) => (
                                <tr key={idx} className="group">
                                    <td className="py-4 px-2">
                                        <input 
                                            value={txn.merchant} 
                                            onChange={(e) => handleUpdate(idx, 'merchant', e.target.value)}
                                            className="bg-transparent border-none text-white text-sm focus:ring-0 w-full outline-none"
                                        />
                                    </td>
                                    <td className="py-4 px-2">
                                        <input 
                                            type="number"
                                            value={txn.amount} 
                                            onChange={(e) => handleUpdate(idx, 'amount', parseFloat(e.target.value))}
                                            className="bg-transparent border-none text-white font-mono text-sm focus:ring-0 w-full outline-none"
                                        />
                                    </td>
                                    <td className="py-4 px-2">
                                        <input 
                                            type="date"
                                            value={txn.date} 
                                            onChange={(e) => handleUpdate(idx, 'date', e.target.value)}
                                            className="bg-transparent border-none text-[#737373] text-xs focus:ring-0 outline-none"
                                        />
                                    </td>
                                    <td className="py-4 px-2">
                                        <select 
                                            value={txn.category} 
                                            onChange={(e) => handleUpdate(idx, 'category', e.target.value)}
                                            className="bg-[#111111] border border-[#262626] rounded-lg px-3 py-1.5 text-xs outline-none text-[#a3a3a3]"
                                        >
                                            {CATEGORIES.map(c => <option key={c} value={c}>{c}</option>)}
                                        </select>
                                    </td>
                                    <td className="py-4 px-2 text-right">
                                        <button onClick={() => setTxns(txns.filter((_, i) => i !== idx))} className="text-[#404040] hover:text-red-400">
                                            <Trash2 size={16} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                <div className="p-8 border-t border-[#262626] flex justify-end gap-4 bg-[#111111]/50">
                    <button onClick={onClose} className="px-6 py-2 rounded-xl text-sm font-medium hover:text-white transition-colors">Dismiss</button>
                    <button onClick={handleSave} className="bg-[#cc9966] text-black px-8 py-2.5 rounded-full text-sm font-bold hover:opacity-90 transition-all flex items-center gap-2">
                        <Check size={18} /> Confirm Entries
                    </button>
                </div>
            </div>
        </div>
    )
}
