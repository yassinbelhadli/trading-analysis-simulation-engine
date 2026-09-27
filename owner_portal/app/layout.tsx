import type { Metadata } from "next";
import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import OwnerAuthGuard from "@/components/auth/owner_auth_guard";
import { ThemeProvider } from "@/components/ThemeProvider";
import { ToastProvider } from "@ds/components/Toast";

const display = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const body = Inter({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ICT Funded EA Pro — Owner Portal",
  description: "Platform Control Plane",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        <ThemeProvider>
          <OwnerAuthGuard>
            <ToastProvider>{children}</ToastProvider>
          </OwnerAuthGuard>
        </ThemeProvider>
      </body>
    </html>
  );
}
