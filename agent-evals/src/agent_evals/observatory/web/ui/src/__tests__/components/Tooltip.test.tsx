import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Tooltip, TooltipProvider } from "../../components/Tooltip";

function renderTooltip(content: string = "Tip text") {
  return render(
    <TooltipProvider delayDuration={0}>
      <Tooltip content={content}>
        <button>Hover me</button>
      </Tooltip>
    </TooltipProvider>,
  );
}

describe("Tooltip", () => {
  it("should render the trigger element", () => {
    renderTooltip();
    expect(screen.getByRole("button", { name: "Hover me" })).toBeInTheDocument();
  });

  it("should not show tooltip content initially", () => {
    renderTooltip();
    expect(screen.queryByText("Tip text")).not.toBeInTheDocument();
  });

  it("should show tooltip content on hover", async () => {
    const user = userEvent.setup();
    renderTooltip();
    await user.hover(screen.getByRole("button", { name: "Hover me" }));
    expect(await screen.findByRole("tooltip")).toBeInTheDocument();
  });

  it("should export TooltipProvider", () => {
    expect(TooltipProvider).toBeDefined();
  });
});
