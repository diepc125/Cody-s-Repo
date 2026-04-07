import { BarChart2, TrendingUp, MessageSquare, Search } from "lucide-react";

export type Tab = "overview" | "charts" | "social" | "analysis";

interface TabNavProps {
  active: Tab;
  onChange: (tab: Tab) => void;
}

const TABS: { id: Tab; label: string; description: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Screener",    description: "Scan all stocks and filter by signal",       icon: <BarChart2 size={14} /> },
  { id: "charts",   label: "Charts",      description: "Price history and sentiment over time",       icon: <TrendingUp size={14} /> },
  { id: "social",   label: "Social Buzz", description: "What Reddit and social media are saying",    icon: <MessageSquare size={14} /> },
  { id: "analysis", label: "Deep Dive",   description: "Full signal breakdown for a selected stock", icon: <Search size={14} /> },
];

export function TabNav({ active, onChange }: TabNavProps) {
  return (
    <div className="tab-nav">
      {TABS.map((tab) => (
        <button
          key={tab.id}
          className={`tab-btn ${active === tab.id ? "active" : ""}`}
          onClick={() => onChange(tab.id)}
          title={tab.description}
        >
          {tab.icon}
          {tab.label}
        </button>
      ))}
    </div>
  );
}
