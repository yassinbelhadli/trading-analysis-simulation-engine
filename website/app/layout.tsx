import type { Metadata } from "next";
import { Space_Grotesk, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import WebsiteShell from "@/components/layout/WebsiteShell";

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
  title: {
    default: "ICT Funded EA Pro — Funded Account Trading EA",
    template: "%s | ICT Funded EA Pro",
  },
  description:
    "ICT Funded EA Pro is a disciplined algorithmic trading EA for funded-account traders. Market-structure execution, funded-rule compliance, and capital protection on MetaTrader 4 and 5.",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>
        <WebsiteShell>{children}</WebsiteShell>
      </body>
    </html>
  );
}
