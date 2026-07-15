import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SAS — Academic Scheduler",
  description:
    "AI-powered, conflict-free school timetable generation (OR-Tools CP-SAT).",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
