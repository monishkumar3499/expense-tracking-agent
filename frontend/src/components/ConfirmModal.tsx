'use client'

import React from 'react'

interface ConfirmModalProps {
    isOpen: boolean
    title: string
    message: string
    onConfirm: () => void
    onCancel: () => void
    confirmText?: string
    cancelText?: string
    variant?: 'danger' | 'primary'
}

export default function ConfirmModal({ 
    isOpen, 
    title, 
    message, 
    onConfirm, 
    onCancel, 
    confirmText = "Confirm", 
    cancelText = "Cancel",
    variant = 'primary'
}: ConfirmModalProps) {
    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-[200] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-300">
            <div className="bg-white w-full max-w-md rounded-[2.5rem] p-10 shadow-2xl space-y-6 animate-in zoom-in duration-300">
                <div className="space-y-2 text-center">
                    <h3 className="text-2xl font-bold text-[#171717]">{title}</h3>
                    <p className="text-[#a3a3a3] text-sm font-medium leading-relaxed">
                        {message}
                    </p>
                </div>

                <div className="flex flex-col gap-3 pt-4">
                    <button 
                        onClick={onConfirm}
                        className={`w-full py-4 rounded-2xl font-bold transition-all shadow-lg ${
                            variant === 'danger' 
                                ? 'bg-[#ef4444] text-white shadow-red-500/20 hover:bg-[#dc2626]' 
                                : 'bg-[#171717] text-white shadow-black/10 hover:opacity-90'
                        }`}
                    >
                        {confirmText}
                    </button>
                    <button 
                        onClick={onCancel}
                        className="w-full py-4 border border-[#e5e5e5] rounded-2xl font-bold text-[#737373] hover:bg-[#f5f5f5] transition-all"
                    >
                        {cancelText}
                    </button>
                </div>
            </div>
        </div>
    )
}
