import { describe, it, expect, beforeEach } from "vitest";
import { renderHook } from "@testing-library/react";
import { useDocumentTitle } from "../../hooks/useDocumentTitle";

describe("useDocumentTitle", () => {
  beforeEach(() => {
    document.title = "Default";
  });

  it("should set document title with Observatory suffix", () => {
    renderHook(() => useDocumentTitle("Run Config"));
    expect(document.title).toBe("Run Config | Observatory");
  });

  it("should restore previous title on unmount", () => {
    const { unmount } = renderHook(() => useDocumentTitle("History"));
    expect(document.title).toBe("History | Observatory");
    unmount();
    expect(document.title).toBe("Default");
  });

  it("should update title when argument changes", () => {
    const { rerender } = renderHook(
      ({ title }) => useDocumentTitle(title),
      { initialProps: { title: "Page A" } },
    );
    expect(document.title).toBe("Page A | Observatory");
    rerender({ title: "Page B" });
    expect(document.title).toBe("Page B | Observatory");
  });
});
