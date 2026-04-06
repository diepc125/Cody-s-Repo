import { BarChart2, TrendingUp, Newspaper, PieChart } from "lucide-react";

export type Tab = "overview" | "charts" | "social" | "analysis";

interface TabNavProps {
  active: Tab;
  onChange: (tab: Tab) => void;
}

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Screener", icon: <BarChart2 size={14} /> },
  { id: "charts",   label: "Charts",   icon: <TrendingUp size={14} /> },
  { id: "social",   label: "Social",   icon: <PieChart size={14} /> },
  { id: "analysis", label: "Analysis", icon: <Newspaper size={14} /> },
];

export function TabNav({ active, onChange }: TabNavProps) {
  return (
    <div className="tab-nav">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          className={`tab-btn ${active === tab.id ? "active" : ""}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </div>
  );
}
