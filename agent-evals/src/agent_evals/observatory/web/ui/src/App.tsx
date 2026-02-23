import { Routes, Route, NavLink } from "react-router-dom";
import {
  Play,
  Activity,
  BarChart3,
  Eye,
  History,
  Cpu,
} from "lucide-react";
import { cn } from "./lib/utils";
import RunConfig from "./pages/RunConfig";
import LiveMonitor from "./pages/LiveMonitor";
import { ResultsExplorer } from "./pages/ResultsExplorer";
import { Observatory } from "./pages/Observatory";
import { History as HistoryPage } from "./pages/History";
import { Models } from "./pages/Models";

const navItems = [
  { to: "/", label: "Run Config", icon: Play },
  { to: "/live", label: "Live Monitor", icon: Activity },
  { to: "/results", label: "Results", icon: BarChart3 },
  { to: "/observatory", label: "Observatory", icon: Eye },
  { to: "/history", label: "History", icon: History },
  { to: "/models", label: "Models", icon: Cpu },
] as const;

export default function App() {
  return (
    <div className="min-h-screen bg-brand-cream">
      <nav className="border-b border-brand-mist bg-brand-bone">
        <div className="mx-auto flex max-w-full items-center gap-sp-1 px-sp-6 py-sp-3">
          <span className="mr-sp-6 font-display text-h5 text-brand-charcoal tracking-headline">
            Observatory
          </span>
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "inline-flex items-center gap-sp-2 rounded-card px-sp-4 py-sp-2",
                  "text-body-sm font-medium transition-colors duration-micro",
                  isActive
                    ? "bg-brand-goldenrod/10 text-brand-goldenrod"
                    : "text-brand-slate hover:text-brand-charcoal hover:bg-brand-cream",
                )
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </div>
      </nav>

      <main>
        <Routes>
          <Route path="/" element={<RunConfig />} />
          <Route path="/live/:runId?" element={<LiveMonitor />} />
          <Route path="/results/:runId?" element={<ResultsExplorer />} />
          <Route path="/observatory" element={<Observatory />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/models" element={<Models />} />
        </Routes>
      </main>
    </div>
  );
}
