import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";
import { AuthProviderWrapper } from "@/components/auth-provider";
import { WebVitals } from "@/components/telemetry/web-vitals";
import { TelemetryBootstrap } from "@/components/telemetry/telemetry-bootstrap";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Brasaland Backoffice",
  description:
    "Panel interno para operaciones, compras y monitoreo de logica de negocio.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={`${inter.variable} ${jakarta.variable}`}>
      <body>
        <WebVitals />
        <TelemetryBootstrap />
        <AuthProviderWrapper>{children}</AuthProviderWrapper>
      </body>
    </html>
  );
}
