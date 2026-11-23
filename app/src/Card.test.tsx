// @vitest-environment jsdom
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import Card from "./Card";
import { cardFields } from "./cards";

afterEach(cleanup);

describe("<Card> (#36)", () => {
  it("shows a visible Missing label for a missing field and never a default value", () => {
    render(<Card fields={cardFields([{ kind: "definition", body: "Bâtiment." }])} />);
    const register = screen.getByText("Register").closest("div")!;
    expect(within(register).getByText("Missing")).toBeTruthy();
    for (const fallback of ["neutral", "Neutral", "Casual", "Frozen"]) {
      expect(screen.queryByText(fallback)).toBeNull();
    }
    expect(screen.getAllByText("Missing")).toHaveLength(3); // register, emotional colour, example
    expect(screen.getByText("Bâtiment.")).toBeTruthy();
  });
});
