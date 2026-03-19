import type { Metadata } from "next";
import "./globals.css";
import { LocaleProvider } from "@/lib/i18n/LocaleContext";
import { NavBar } from "@/components/NavBar";

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
        <LocaleProvider>
          <NavBar />
          <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
        </LocaleProvider>
      </body>
    </html>
  );
}
