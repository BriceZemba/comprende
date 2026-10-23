import type { Metadata, Viewport } from "next";
import { Fraunces, Inter } from "next/font/google";
import { I18nProvider } from "@/lib/i18n";
import "./globals.css";

const fraunces = Fraunces({ variable: "--font-fraunces", subsets: ["latin"], axes: ["opsz", "SOFT"] });
const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  metadataBase: new URL("https://comprende.vercel.app"),
  title: "Comprende: Spanish you'll love and understand",
  description:
    "Find Spanish films and series that match your taste and your level. Taste from the Qloo taste graph, difficulty measured from real subtitles.",
  openGraph: { type: "website", siteName: "Comprende", url: "https://comprende.vercel.app" },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fbf7f1" },
    { media: "(prefers-color-scheme: dark)", color: "#15120f" },
  ],
};

// Applies the saved theme and language before first paint, so a dark-mode visitor never sees a light flash.
const NO_FLASH = `try{var d=document.documentElement,t=localStorage.getItem('theme');if(t==='light'||t==='dark')d.dataset.theme=t;var l=localStorage.getItem('lang');if(l==='en'||l==='fr'||l==='es')d.lang=l}catch(e){}`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: NO_FLASH }} />
      </head>
      <body className={`${fraunces.variable} ${inter.variable} antialiased`}>
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}
