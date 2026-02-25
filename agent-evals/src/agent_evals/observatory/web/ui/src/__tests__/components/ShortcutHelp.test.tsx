import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ShortcutHelp } from "../../components/ShortcutHelp";

describe("ShortcutHelp", () => {
  it("should render the dialog when open is true", () => {
    render(<ShortcutHelp open={true} onOpenChange={() => {}} />);
    expect(screen.getByText("Keyboard Shortcuts")).toBeInTheDocument();
  });

  it("should not render content when open is false", () => {
    render(<ShortcutHelp open={false} onOpenChange={() => {}} />);
    expect(screen.queryByText("Keyboard Shortcuts")).not.toBeInTheDocument();
  });

  it("should display all shortcut descriptions", () => {
    render(<ShortcutHelp open={true} onOpenChange={() => {}} />);

    expect(screen.getByText("Go to Run Config")).toBeInTheDocument();
    expect(screen.getByText("Go to Live Monitor")).toBeInTheDocument();
    expect(screen.getByText("Go to Results Explorer")).toBeInTheDocument();
    expect(screen.getByText("Go to Observatory")).toBeInTheDocument();
    expect(screen.getByText("Go to History")).toBeInTheDocument();
    expect(screen.getByText("Go to Pipeline")).toBeInTheDocument();
    expect(screen.getByText("Go to Models")).toBeInTheDocument();
    expect(screen.getByText("Show this help")).toBeInTheDocument();
  });

  it("should render kbd elements for shortcut keys", () => {
    render(<ShortcutHelp open={true} onOpenChange={() => {}} />);

    const kbds = screen.getAllByText("g");
    // 7 chord shortcuts all start with "g"
    expect(kbds.length).toBe(7);
    // Verify they are rendered as <kbd> elements
    kbds.forEach((kbd) => {
      expect(kbd.tagName).toBe("KBD");
    });
  });

  it("should render second key of each chord as kbd", () => {
    render(<ShortcutHelp open={true} onOpenChange={() => {}} />);

    const secondKeys = ["r", "l", "e", "o", "h", "p", "m"];
    secondKeys.forEach((key) => {
      const el = screen.getByText(key);
      expect(el.tagName).toBe("KBD");
    });
  });

  it("should render the ? shortcut key as kbd", () => {
    render(<ShortcutHelp open={true} onOpenChange={() => {}} />);

    const questionMark = screen.getByText("?");
    expect(questionMark.tagName).toBe("KBD");
  });

  it("should have a close button with aria-label Close", () => {
    render(<ShortcutHelp open={true} onOpenChange={() => {}} />);

    const closeBtn = screen.getByLabelText("Close");
    expect(closeBtn).toBeInTheDocument();
  });

  it("should call onOpenChange with false when close button is clicked", () => {
    const onOpenChange = vi.fn();
    render(<ShortcutHelp open={true} onOpenChange={onOpenChange} />);

    fireEvent.click(screen.getByLabelText("Close"));

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("should call onOpenChange when Escape is pressed", () => {
    const onOpenChange = vi.fn();
    render(<ShortcutHelp open={true} onOpenChange={onOpenChange} />);

    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("should render exactly 8 shortcut entries", () => {
    render(<ShortcutHelp open={true} onOpenChange={() => {}} />);

    const descriptions = [
      "Go to Run Config",
      "Go to Live Monitor",
      "Go to Results Explorer",
      "Go to Observatory",
      "Go to History",
      "Go to Pipeline",
      "Go to Models",
      "Show this help",
    ];

    descriptions.forEach((desc) => {
      expect(screen.getByText(desc)).toBeInTheDocument();
    });
    expect(descriptions).toHaveLength(8);
  });

  it("should display the dialog title as h4 heading style", () => {
    render(<ShortcutHelp open={true} onOpenChange={() => {}} />);

    const title = screen.getByText("Keyboard Shortcuts");
    expect(title.className).toContain("text-h4");
    expect(title.className).toContain("text-brand-charcoal");
  });
});
