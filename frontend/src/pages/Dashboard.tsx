import { useEffect, useState } from "react";
import { getHealth } from "../api/client";

export default function Dashboard() {
  const [health, setHealth] = useState<string>("checking...");

  useEffect(() => {
    getHealth()
      .then((data) => setHealth(data.status))
      .catch(() => setHealth("unreachable"));
  }, []);

  return (
    <div>
      <h1>Dashboard</h1>
      <p style={{ color: "#666" }}>Welcome to Travel Invoice Assistant</p>

      <div style={{ display: "flex", gap: 16, marginTop: 24 }}>
        <StatCard label="Backend Status" value={health} />
        <StatCard label="Trips This Month" value="0" />
        <StatCard label="Pending Review" value="0" />
        <StatCard label="Issues" value="0" />
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        background: "#fff",
        borderRadius: 8,
        padding: "20px 28px",
        boxShadow: "0 1px 4px rgba(0,0,0,0.08)",
        minWidth: 160,
      }}
    >
      <div style={{ fontSize: 13, color: "#888", marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 600 }}>{value}</div>
    </div>
  );
}