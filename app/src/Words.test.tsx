// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fetchWordsPage = vi.hoisted(() => vi.fn());
vi.mock("./wordsPage", async (importActual) => ({
  ...(await importActual<typeof import("./wordsPage")>()),
  fetchWordsPage,
}));

import Words from "./Words";

const word = (n: number) => ({
  id: `id${n}`, surface_form: `word${n}`, lemma: `word${n}`, language: "French",
  created_at: `2026-11-17T10:${String(59 - n).padStart(2, "0")}:00Z`, notes: [],
});
const page = (from: number, to: number) => Array.from({ length: to - from }, (_, i) => word(from + i));

beforeEach(() => {
  fetchWordsPage.mockReset();
  // jsdom has no IntersectionObserver; the "Load more" button covers it.
  vi.stubGlobal("IntersectionObserver", undefined);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("My words pagination", () => {
  it("shows the total from the database, not the number of rows loaded", async () => {
    fetchWordsPage.mockResolvedValueOnce({ rows: page(0, 50), total: 1234, cursor: { id: "id49", created_at: "x" } });

    render(<Words version={0} />);

    expect(await screen.findByText("1234")).toBeTruthy();
    expect(fetchWordsPage).toHaveBeenCalledWith(null);
  });

  it("loads the next page after the last word shown, and appends it", async () => {
    fetchWordsPage
      .mockResolvedValueOnce({ rows: page(0, 50), total: 60, cursor: { id: "id49", created_at: "c49" } })
      .mockResolvedValueOnce({ rows: page(50, 60), total: null, cursor: null });

    render(<Words version={0} />);
    await screen.findByText("word0");

    await act(async () => fireEvent.click(screen.getByRole("button", { name: /load more/i })));

    await waitFor(() => expect(screen.getByText("word59")).toBeTruthy());
    expect(fetchWordsPage).toHaveBeenLastCalledWith({ id: "id49", created_at: "c49" });
    expect(screen.getByText("word0")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /load more/i })).toBeNull();
  });
});

describe("My words after a failed read", () => {
  it("offers Retry when the first page fails, and retrying loads the words", async () => {
    fetchWordsPage
      .mockRejectedValueOnce(new Error("Network request failed"))
      .mockResolvedValueOnce({ rows: page(0, 3), total: 3, cursor: null });

    render(<Words version={0} />);
    expect(await screen.findByText("Network request failed")).toBeTruthy();

    await act(async () => fireEvent.click(screen.getByRole("button", { name: /retry/i })));

    expect(await screen.findByText("word0")).toBeTruthy();
    expect(fetchWordsPage).toHaveBeenCalledTimes(2);
    expect(fetchWordsPage).toHaveBeenLastCalledWith(null);
  });

  it("keeps the loaded words when Load more fails, and retries just that page", async () => {
    fetchWordsPage
      .mockResolvedValueOnce({ rows: page(0, 50), total: 60, cursor: { id: "id49", created_at: "c49" } })
      .mockRejectedValueOnce(new Error("Network request failed"))
      .mockResolvedValueOnce({ rows: page(50, 60), total: null, cursor: null });

    render(<Words version={0} />);
    await screen.findByText("word0");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /load more/i })));

    expect(await screen.findByText("Network request failed")).toBeTruthy();
    expect(screen.getByText("word0")).toBeTruthy(); // the list is still there

    await act(async () => fireEvent.click(screen.getByRole("button", { name: /retry/i })));

    await waitFor(() => expect(screen.getByText("word59")).toBeTruthy());
    expect(fetchWordsPage).toHaveBeenLastCalledWith({ id: "id49", created_at: "c49" });
  });
});
