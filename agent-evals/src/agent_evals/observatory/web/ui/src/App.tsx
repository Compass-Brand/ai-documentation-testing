import { useState } from "react";
import { Routes, Route, NavLink, useLocation } from "react-router-dom";
import {
  Play,
  Activity,
  BarChart3,
  Eye,
  History,
  GitBranch,
  Cpu,
  Compass,
} from "lucide-react";
import { cn } from "./lib/utils";
import { ScrollThread } from "./components/ScrollThread";
import { useKeyboardShortcuts } from "./hooks/useKeyboardShortcuts";
import { ShortcutHelp } from "./components/ShortcutHelp";
import RunConfig from "./pages/RunConfig";
import LiveMonitor from "./pages/LiveMonitor";
import { ResultsExplorer } from "./pages/ResultsExplorer";
import { Observatory } from "./pages/Observatory";
import { History as HistoryPage } from "./pages/History";
import { Models } from "./pages/Models";
import { FactorAnalysis } from "./pages/FactorAnalysis";
import { PipelineView } from "./pages/PipelineView";

const navItems = [
  { to: "/", label: "Run Config", icon: Play },
  { to: "/live", label: "Live Monitor", icon: Activity },
  { to: "/results", label: "Results", icon: BarChart3 },
  { to: "/observatory", label: "Observatory", icon: Eye },
  { to: "/history", label: "History", icon: History },
  { to: "/pipeline", label: "Pipeline", icon: GitBranch },
  { to: "/models", label: "Models", icon: Cpu },
] as const;

export default function App() {
  const location = useLocation();
  const [helpOpen, setHelpOpen] = useState(false);
  useKeyboardShortcuts(() => setHelpOpen(true));

  return (
    <div className="min-h-screen bg-brand-cream">
      <ScrollThread />
      <ShortcutHelp open={helpOpen} onOpenChange={setHelpOpen} />
      <nav className="sticky top-0 z-40 border-b border-brand-mist backdrop-blur-md bg-brand-bone/90">
        <div className="mx-auto flex max-w-full items-center gap-sp-1 px-sp-6 py-sp-3">
          <Compass className="mr-sp-2 h-5 w-5 text-brand-goldenrod" />
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
                  "inline-flex items-center gap-sp-2 px-sp-4 py-sp-2",
                  "text-body-sm font-medium transition-all duration-micro",
                  "border-b-2",
                  isActive
                    ? "border-brand-goldenrod text-brand-goldenrod"
                    : "border-transparent text-brand-slate hover:text-brand-charcoal hover:border-brand-mist",
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
        <div key={location.pathname} className="animate-fade-in-up">
          <Routes>
            <Route path="/" element={<RunConfig />} />
            <Route path="/live/:runId?" element={<LiveMonitor />} />
            <Route path="/results/:runId?" element={<ResultsExplorer />} />
            <Route path="/observatory" element={<Observatory />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/models" element={<Models />} />
            <Route path="/analysis/:runId" element={<FactorAnalysis />} />
            <Route path="/pipeline/:pipelineId?" element={<PipelineView />} />
            <Route
              path="*"
              element={
                <div className="flex flex-col items-center justify-center py-sp-16 text-center">
                  <h1 className="text-h2 text-brand-charcoal mb-sp-4">
                    Page Not Found
                  </h1>
                  <p className="text-body text-brand-slate">
                    The page you're looking for doesn't exist.
                  </p>
                </div>
              }
            />
          </Routes>
        </div>
      </main>
    </div>
  );
}
