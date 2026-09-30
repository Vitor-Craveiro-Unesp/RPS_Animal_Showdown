import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "RPS: Animal Showdown",
  description: "Tournament platform scaffold"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
