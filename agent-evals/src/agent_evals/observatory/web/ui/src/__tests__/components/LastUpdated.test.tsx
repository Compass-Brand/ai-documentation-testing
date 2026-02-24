import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { LastUpdated } from "../../components/LastUpdated";

describe("LastUpdated", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("shows -- when timestamp is null", () => {
    render(<LastUpdated timestamp={null} />);
    expect(screen.getByText("--")).toBeInTheDocument();
  });

  it("shows seconds ago for recent timestamps", () => {
    const now = Date.now();
    vi.setSystemTime(now);
    render(<LastUpdated timestamp={now - 5000} />);
    expect(screen.getByText("5s ago")).toBeInTheDocument();
  });

  it("shows minutes ago for older timestamps", () => {
    const now = Date.now();
    vi.setSystemTime(now);
    render(<LastUpdated timestamp={now - 180_000} />);
    expect(screen.getByText("3m ago")).toBeInTheDocument();
  });

  it("shows hours ago for timestamps over an hour old", () => {
    const now = Date.now();
    vi.setSystemTime(now);
    render(<LastUpdated timestamp={now - 7_200_000} />);
    expect(screen.getByText("2h ago")).toBeInTheDocument();
  });

  it("accepts Date objects", () => {
    const now = Date.now();
    vi.setSystemTime(now);
    render(<LastUpdated timestamp={new Date(now - 30_000)} />);
    expect(screen.getByText("30s ago")).toBeInTheDocument();
  });
});
