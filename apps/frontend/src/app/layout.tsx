import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "RPS: Animal Showdown",
  description: "A live animal RPS tournament arena"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
