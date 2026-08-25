import { redirect } from "next/navigation";

/** Legacy URLs with query id - session only keeps the latest trace at /query. */
export default function LegacyQueryTracePage() {
  redirect("/query");
}
