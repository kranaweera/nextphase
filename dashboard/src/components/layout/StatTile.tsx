import type { ReactNode } from "react";

interface StatTileProps {
  label: string;
  value: ReactNode;
}

export default function StatTile({ label, value }: StatTileProps) {
  return (
    <div className="stat-tile">
      <span className="stat-label">{label}</span>
      <span className="stat-value">{value}</span>
    </div>
  );
}
