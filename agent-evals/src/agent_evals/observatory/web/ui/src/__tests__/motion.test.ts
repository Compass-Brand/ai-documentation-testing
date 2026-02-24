import { describe, it, expect } from "vitest";
import { TRANSITIONS } from "../lib/motion";

describe("motion TRANSITIONS", () => {
  it("should export micro transition preset", () => {
    expect(TRANSITIONS.micro).toContain("150ms");
  });

  it("should export state transition preset", () => {
    expect(TRANSITIONS.state).toContain("250ms");
  });

  it("should export page transition preset", () => {
    expect(TRANSITIONS.page).toContain("350ms");
  });

  it("should export modal transition preset", () => {
    expect(TRANSITIONS.modal).toContain("250ms");
  });
});
