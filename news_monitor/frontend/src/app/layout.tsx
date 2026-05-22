import type { Metadata } from "next";
import { DM_Sans } from "next/font/google";
import { Noto_Nastaliq_Urdu } from "next/font/google";
import "./globals.css";
import { siteConfig } from "@/config/site";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["400", "500", "600", "700"],
});

const notoUrdu = Noto_Nastaliq_Urdu({
  subsets: ["arabic"],
  variable: "--font-urdu",
  weight: ["400", "700"],
});

export const metadata: Metadata = {
  title: `${siteConfig.name} Dashboard`,
  description: siteConfig.description,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" dir={siteConfig.direction}>
      <body
        className={`${dmSans.variable} ${notoUrdu.variable} font-sans antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
