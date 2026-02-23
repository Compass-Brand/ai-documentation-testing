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

function Placeholder({ name }: { name: string }) {
  return (
    <div className="px-sp-6 py-sp-8">
      <h1 className="text-h2 text-brand-charcoal">{name}</h1>
      <p className="text-body text-brand-slate mt-sp-2">Coming soon.</p>
    </div>
  );
}

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
          <Route path="/" element={<Placeholder name="Run Configuration" />} />
          <Route path="/live/:runId?" element={<Placeholder name="Live Monitor" />} />
          <Route path="/results/:runId?" element={<Placeholder name="Results Explorer" />} />
          <Route path="/observatory" element={<Placeholder name="Observatory" />} />
          <Route path="/history" element={<Placeholder name="History" />} />
          <Route path="/models" element={<Placeholder name="Models" />} />
        </Routes>
      </main>
    </div>
  );
}
