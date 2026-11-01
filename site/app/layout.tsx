import type { Metadata, Viewport } from "next";
import localFont from "next/font/local";
import "./globals.css";

// Anek Devanagari, self-hosted and subset to Latin + ₹ (115 KB, both axes kept); see
// app/fonts/README.txt. Devanagari text uses the phone's own font (Noto Sans Devanagari).
const anek = localFont({
  src: "./fonts/AnekDevanagari-Latin-wdth-wght.woff2",
  weight: "100 800",
  variable: "--font-anek",
  display: "swap",
});

const title = "Kirana Khata: bolo, aur hisaab likh jayega";
const description =
  "Dukaan ka udhaar, jama aur bikri, sirf bolkar. Kirana Khata sunta hai, dohraata hai, aur aapke haan ke baad hi likhta hai.";

export const metadata: Metadata = {
  title,
  description,
  applicationName: "Kirana Khata",
  icons: { icon: "/icon.svg", apple: "/apple-touch-icon.png" },
  openGraph: { title, description, type: "website", locale: "hi_IN" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#1B2559",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="hi" className={anek.variable}>
      <body>{children}</body>
    </html>
  );
}
