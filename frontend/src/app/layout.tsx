import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Site Layout Tool - Pacifico Energy',
  description: 'Automated site layout generation for BESS projects',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
