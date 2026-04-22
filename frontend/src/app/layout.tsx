import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "react-hot-toast";
import Sidebar from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Finn 💸 Personal Expense Agent",
  description: "AI-powered personal finance assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} flex min-h-screen bg-white text-[#171717]`}>
        <Sidebar />
        <main className="flex-1 flex flex-col min-h-screen relative">
          {children}
        </main>
        <Toaster 
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#ffffff',
              color: '#171717',
              border: '1px solid #e5e5e5',
              borderRadius: '16px',
              fontSize: '14px',
              padding: '12px 16px',
            },
          }}
        />
      </body>
    </html>
  );
}
