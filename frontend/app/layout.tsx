import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Retail Forecast Platform",
  description: "Data-driven forecasting and AI decision support",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-950 text-slate-100 antialiased">
        <nav className="border-b border-slate-800 bg-slate-900/50 px-6 py-4">
          <div className="mx-auto flex max-w-6xl items-center gap-6">
            <a href="/" className="text-lg font-semibold text-emerald-400">
              Retail Forecast
            </a>
            <a href="/forecast" className="text-slate-400 hover:text-white">
              Forecast
            </a>
            <a href="/data" className="text-slate-400 hover:text-white">
              Data
            </a>
            <a href="/assistant" className="text-slate-400 hover:text-white">
              AI Assistant
            </a>
            <a href="/knowledge" className="text-slate-400 hover:text-white">
              Knowledge
            </a>
          </div>
        </nav>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
