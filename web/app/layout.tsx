import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "../lib/session";

export const metadata: Metadata = {
  title: "Redactinator",
  description: "Secure document redaction landing page",
  icons: {
    icon: "/logo.png",
  },
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
