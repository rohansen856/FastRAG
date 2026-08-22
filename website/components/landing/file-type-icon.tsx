import {
  Braces,
  FileCode2,
  FileSpreadsheet,
  FileText,
  Sheet,
} from "lucide-react";
import { fileExtension } from "@/lib/upload";

const PDF_CLASS = "text-red-600";
const TEXT_CLASS = "text-blue-600";
const DATA_CLASS = "text-emerald-600";
const MARKUP_CLASS = "text-violet-600";
const DEFAULT_CLASS = "text-muted-foreground";

export function FileTypeIcon({
  filename,
  className = "w-4 h-4",
  disabled = false,
}: {
  filename: string;
  className?: string;
  disabled?: boolean;
}) {
  const ext = fileExtension(filename);
  const iconClass = `${className} shrink-0 ${disabled ? "text-muted-foreground/35" : ""}`;

  if (disabled) {
    return <FileText className={iconClass} aria-hidden />;
  }

  if (ext === ".pdf") {
    return <FileText className={`${iconClass} ${PDF_CLASS}`} aria-hidden />;
  }
  if ([".md", ".markdown", ".txt", ".log", ".rst"].includes(ext)) {
    return <FileText className={`${iconClass} ${TEXT_CLASS}`} aria-hidden />;
  }
  if ([".json", ".jsonl"].includes(ext)) {
    return <Braces className={`${iconClass} ${DATA_CLASS}`} aria-hidden />;
  }
  if ([".csv", ".tsv"].includes(ext)) {
    return <FileSpreadsheet className={`${iconClass} ${DATA_CLASS}`} aria-hidden />;
  }
  if ([".html", ".htm", ".xml"].includes(ext)) {
    return <FileCode2 className={`${iconClass} ${MARKUP_CLASS}`} aria-hidden />;
  }
  if ([".yaml", ".yml"].includes(ext)) {
    return <Sheet className={`${iconClass} ${MARKUP_CLASS}`} aria-hidden />;
  }
  return <FileText className={`${iconClass} ${DEFAULT_CLASS}`} aria-hidden />;
}
