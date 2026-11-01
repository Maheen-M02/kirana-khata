import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";

import { SwRegister } from "@/components/sw-register";

// Anek Devanagari, self-hosted and subset to Latin + ₹ (115 KB, both axes kept); see
// app/fonts/README.txt. Devanagari text uses the phone's own font (Noto Sans Devanagari).
const anek = localFont({
  src: "./fonts/AnekDevanagari-Latin-wdth-wght.woff2",
  weight: "100 800",
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
