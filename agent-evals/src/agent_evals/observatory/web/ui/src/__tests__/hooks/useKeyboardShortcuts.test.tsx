import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { createElement } from "react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

const mockNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return { ...actual, useNavigate: () => mockNavigate };
});

function createWrapper() {
  return function Wrapper({ children }: { children: ReactNode }) {
    return createElement(MemoryRouter, null, children);
  };
}

function fireKey(
  key: string,
  target?: HTMLElement,
  opts?: Partial<KeyboardEvent>,
) {
  const event = new KeyboardEvent("keydown", {
    key,
    bubbles: true,
    ...opts,
  });
  // Dispatch from the target element so the DOM sets e.target correctly;
  // with bubbles: true the event will reach the document listener.
  (target ?? document).dispatchEvent(event);
}

describe("useKeyboardShortcuts", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockNavigate.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("should navigate to / when g then r is pressed", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g"));
    act(() => fireKey("r"));

    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("should navigate to /live when g then l is pressed", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g"));
    act(() => fireKey("l"));

    expect(mockNavigate).toHaveBeenCalledWith("/live");
  });

  it("should navigate to /models when g then m is pressed", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g"));
    act(() => fireKey("m"));

    expect(mockNavigate).toHaveBeenCalledWith("/models");
  });

  it("should navigate to /results when g then e is pressed", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g"));
    act(() => fireKey("e"));

    expect(mockNavigate).toHaveBeenCalledWith("/results");
  });

  it("should navigate to /observatory when g then o is pressed", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g"));
    act(() => fireKey("o"));

    expect(mockNavigate).toHaveBeenCalledWith("/observatory");
  });

  it("should navigate to /history when g then h is pressed", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g"));
    act(() => fireKey("h"));

    expect(mockNavigate).toHaveBeenCalledWith("/history");
  });

  it("should navigate to /pipeline when g then p is pressed", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g"));
    act(() => fireKey("p"));

    expect(mockNavigate).toHaveBeenCalledWith("/pipeline");
  });

  it("should call onHelpOpen when ? is pressed", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    const helpFn = vi.fn();
    renderHook(() => useKeyboardShortcuts(helpFn), {
      wrapper: createWrapper(),
    });

    act(() => fireKey("?"));

    expect(helpFn).toHaveBeenCalledOnce();
  });

  it("should not navigate when chord times out", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g"));

    // Advance past the 800ms chord timeout
    act(() => {
      vi.advanceTimersByTime(900);
    });

    act(() => fireKey("r"));

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("should navigate when second key is within timeout", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g"));

    // Advance partway but stay within the 800ms window
    act(() => {
      vi.advanceTimersByTime(500);
    });

    act(() => fireKey("r"));

    expect(mockNavigate).toHaveBeenCalledWith("/");
  });

  it("should not fire shortcuts when typing in an input element", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    const helpFn = vi.fn();
    renderHook(() => useKeyboardShortcuts(helpFn), {
      wrapper: createWrapper(),
    });

    const input = document.createElement("input");
    document.body.appendChild(input);

    act(() => fireKey("?", input));
    expect(helpFn).not.toHaveBeenCalled();

    act(() => fireKey("g", input));
    act(() => fireKey("r", input));
    expect(mockNavigate).not.toHaveBeenCalled();

    document.body.removeChild(input);
  });

  it("should not fire shortcuts when typing in a textarea", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    const helpFn = vi.fn();
    renderHook(() => useKeyboardShortcuts(helpFn), {
      wrapper: createWrapper(),
    });

    const textarea = document.createElement("textarea");
    document.body.appendChild(textarea);

    act(() => fireKey("?", textarea));
    expect(helpFn).not.toHaveBeenCalled();

    document.body.removeChild(textarea);
  });

  it("should not fire shortcuts when typing in a select element", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    const helpFn = vi.fn();
    renderHook(() => useKeyboardShortcuts(helpFn), {
      wrapper: createWrapper(),
    });

    const select = document.createElement("select");
    document.body.appendChild(select);

    act(() => fireKey("?", select));
    expect(helpFn).not.toHaveBeenCalled();

    document.body.removeChild(select);
  });

  it("should not fire shortcuts in a contentEditable element", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    const helpFn = vi.fn();
    renderHook(() => useKeyboardShortcuts(helpFn), {
      wrapper: createWrapper(),
    });

    const div = document.createElement("div");
    div.contentEditable = "true";
    // jsdom doesn't implement isContentEditable, so define it manually
    Object.defineProperty(div, "isContentEditable", { value: true });
    document.body.appendChild(div);

    act(() => fireKey("?", div));
    expect(helpFn).not.toHaveBeenCalled();

    document.body.removeChild(div);
  });

  it("should not navigate when single key is pressed without g prefix", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("r"));
    expect(mockNavigate).not.toHaveBeenCalled();

    act(() => fireKey("l"));
    expect(mockNavigate).not.toHaveBeenCalled();

    act(() => fireKey("m"));
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("should not navigate for an unknown chord key", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g"));
    act(() => fireKey("z"));

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("should ignore ? when ctrlKey is held", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    const helpFn = vi.fn();
    renderHook(() => useKeyboardShortcuts(helpFn), {
      wrapper: createWrapper(),
    });

    act(() => fireKey("?", undefined, { ctrlKey: true }));

    expect(helpFn).not.toHaveBeenCalled();
  });

  it("should ignore g when metaKey is held", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    renderHook(() => useKeyboardShortcuts(), { wrapper: createWrapper() });

    act(() => fireKey("g", undefined, { metaKey: true }));
    act(() => fireKey("r"));

    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it("should return pendingG as false initially", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    const { result } = renderHook(() => useKeyboardShortcuts(), {
      wrapper: createWrapper(),
    });

    expect(result.current.pendingG).toBe(false);
  });

  it("should set pendingG to true after pressing g", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    const { result } = renderHook(() => useKeyboardShortcuts(), {
      wrapper: createWrapper(),
    });

    act(() => fireKey("g"));

    expect(result.current.pendingG).toBe(true);
  });

  it("should reset pendingG after chord completes", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    const { result } = renderHook(() => useKeyboardShortcuts(), {
      wrapper: createWrapper(),
    });

    act(() => fireKey("g"));
    expect(result.current.pendingG).toBe(true);

    act(() => fireKey("r"));
    expect(result.current.pendingG).toBe(false);
  });

  it("should reset pendingG after timeout expires", async () => {
    const { useKeyboardShortcuts } = await import(
      "../../hooks/useKeyboardShortcuts"
    );
    const { result } = renderHook(() => useKeyboardShortcuts(), {
      wrapper: createWrapper(),
    });

    act(() => fireKey("g"));
    expect(result.current.pendingG).toBe(true);

    act(() => {
      vi.advanceTimersByTime(900);
    });

    expect(result.current.pendingG).toBe(false);
  });
});
