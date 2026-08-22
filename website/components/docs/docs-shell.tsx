import type { ReactNode } from "react";
import { Navigation } from "@/components/landing/navigation";
import { FooterSection } from "@/components/landing/footer-section";
import { DocsSidebar } from "@/components/docs/docs-sidebar";

export function DocsShell({ children }: { children: ReactNode }) {
  return (
    <main className="relative min-h-screen overflow-x-hidden noise-overlay">
      <Navigation />
      <div className="pt-28 lg:pt-32 pb-16">
        <div className="max-w-[1400px] mx-auto px-6 lg:px-12">
          <div className="grid lg:grid-cols-[220px_minmax(0,1fr)] gap-12 lg:gap-16">
            <DocsSidebar />
            <div className="min-w-0 max-w-3xl">{children}</div>
          </div>
        </div>
      </div>
      <FooterSection />
    </main>
  );
}
