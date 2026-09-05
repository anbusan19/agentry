import type { Metadata } from "next";
import { Geist_Mono, Instrument_Serif } from "next/font/google";
import "./globals.css";

// Both self-hosted by Next at build time — no runtime request to Google, no
// font files in the repo. Exposed as CSS variables that globals.css reads
// (see --serif and --mono-geist).
const instrumentSerif = Instrument_Serif({
  weight: "400",
  style: ["normal", "italic"],
  subsets: ["latin"],
  variable: "--font-instrument-serif",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Agentry — the pantry restocks itself",
  description:
    "An autonomous grocery-ordering agent. Give it a goal, and it plans the order, drives a real quick-commerce storefront, pays from the platform wallet, and only pings you on Telegram when a real decision is needed.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${instrumentSerif.variable} ${geistMono.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
