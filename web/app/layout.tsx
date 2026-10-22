import type { Metadata, Viewport } from "next";
import { Fraunces, Inter } from "next/font/google";
import "./globals.css";

const fraunces = Fraunces({ variable: "--font-fraunces", subsets: ["latin"], axes: ["opsz", "SOFT"] });
const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Comprende: Spanish you'll love and understand",
  description:
    "Find Spanish films and series that match your taste and your level. Taste from the Qloo taste graph, difficulty measured from real subtitles.",
};

export const viewport: Viewport = { themeColor: "#fbf7f1" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${fraunces.variable} ${inter.variable} antialiased`}>{children}</body>
    </html>
  );
}
