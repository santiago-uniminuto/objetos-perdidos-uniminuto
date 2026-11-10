import "@fontsource-variable/bricolage-grotesque/standard.css";
import "@fontsource/atkinson-hyperlegible/400.css";
import "@fontsource/atkinson-hyperlegible/700.css";
import "./globals.css";

import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
  title: { default: "Objetos perdidos UNIMINUTO", template: "%s | Objetos perdidos UNIMINUTO" },
  description: "Objetos que la comunidad reportó como perdidos. Si encontraste uno, llévalo a la oficina de tu sede.",
};

export const viewport: Viewport = { themeColor: "#14284a", width: "device-width", initialScale: 1 };

export default function RaizLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es-CO">
      <body>{children}</body>
    </html>
  );
}
