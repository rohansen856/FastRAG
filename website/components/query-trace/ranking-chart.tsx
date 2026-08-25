"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChunkTrace } from "@/lib/types";

export function RankingChart({ ranked }: { ranked: ChunkTrace[] }) {
  const data = ranked.slice(0, 12).map((row) => ({
    rank: row.rank,
    score: row.score,
    title: row.title,
  }));

  if (!data.length) {
    return <p className="text-sm text-muted-foreground">No rerank scores to chart.</p>;
  }

  return (
    <div className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(0,0,0,0.06)" />
          <XAxis dataKey="rank" tick={{ fontSize: 10 }} label={{ value: "Rank", position: "insideBottom", offset: -2, fontSize: 10 }} />
          <YAxis domain={[0, 1]} tick={{ fontSize: 10 }} />
          <Tooltip
            formatter={(value: number) => [value.toFixed(3), "Score"]}
            labelFormatter={(label) => `Rank ${label}`}
            contentStyle={{ fontSize: 12 }}
          />
          <Line type="monotone" dataKey="score" stroke="rgba(0,0,0,0.7)" strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
