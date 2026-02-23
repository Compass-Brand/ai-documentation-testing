import { describe, it, expect } from "vitest";
import { cn, shortId, formatRunDate, formatRunLabel } from "../lib/utils";

describe("cn", () => {
  it("should merge class names", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("should handle conditional classes", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });

  it("should resolve tailwind conflicts", () => {
    expect(cn("px-4", "px-6")).toBe("px-6");
  });

  it("should handle undefined and null values", () => {
    expect(cn("base", undefined, null, "end")).toBe("base end");
  });
});

describe("shortId", () => {
  it("should return first 8 characters of a long ID", () => {
    expect(shortId("6a70ae6cf373abcd")).toBe("6a70ae6c");
  });

  it("should return full string if shorter than 8 chars", () => {
    expect(shortId("run-1")).toBe("run-1");
  });
});

describe("formatRunDate", () => {
  it("should format ISO date as short human-readable string", () => {
    const result = formatRunDate("2026-02-23T22:05:00Z");
    expect(result).toMatch(/Feb/);
    expect(result).toMatch(/23/);
  });
});

describe("formatRunLabel", () => {
  it("should combine run type, date, status, and short ID", () => {
    const label = formatRunLabel({
      run_id: "6a70ae6cf373abcd",
      run_type: "taguchi",
      status: "completed",
      created_at: "2026-02-23T22:05:00Z",
    });
    expect(label).toContain("taguchi");
    expect(label).toContain("completed");
    expect(label).toContain("6a70ae6c");
    expect(label).toContain("\u00b7");
  });
});
