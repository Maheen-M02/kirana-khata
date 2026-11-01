import type { Metadata, Viewport } from "next";
import { Anek_Devanagari } from "next/font/google";
import "./globals.css";

import { SwRegister } from "@/components/sw-register";

// One family for Latin and Devanagari names; the width axis gives condensed money figures.
const anek = Anek_Devanagari({
  subsets: ["latin", "devanagari"],
  axes: ["wdth"],
  variable: "--font-anek",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Kirana Khata",
  description: "Bolo, aur hisaab likh jayega: voice khata for kirana shops",
  applicationName: "Kirana Khata",
  icons: { icon: "/icon.svg", apple: "/icons/apple-touch-icon.png" },
  appleWebApp: { capable: true, title: "Khata", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#1B2559",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="hi" className={anek.variable}>
      <body>
        {children}
        <SwRegister />
      </body>
    </html>
  );
}
