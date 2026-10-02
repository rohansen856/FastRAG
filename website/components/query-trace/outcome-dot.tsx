import type { Outcome } from "@/lib/types";

const DOT: Record<Outcome, string> = {
  answered: "bg-emerald-600",
  no_answer: "bg-amber-500",
  refused: "bg-rose-600",
};

export function OutcomeDot({ outcome, className = "" }: { outcome: Outcome; className?: string }) {
  return <span aria-hidden className={`inline-block h-2 w-2 shrink-0 rounded-full ${DOT[outcome]} ${className}`} />;
}
