// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const fake = vi.hoisted(() => ({
  invoke: vi.fn(),
  rpc: vi.fn(),
}));
vi.mock("./supabase", async (importActual) => ({
  ...(await importActual<typeof import("./supabase")>()),
  supabase: { functions: { invoke: fake.invoke }, rpc: fake.rpc },
}));

import AddWord from "./AddWord";

// What generate-word returns from the shared cache.
const generated = {
  word_id: "w-maison",
  word: "maisons",
  language: "French",
  lemma: "maison",
  source: "cache",
  definition: "Bâtiment d'habitation.",
  example: "Ma maison est grande.",
  register: "Casual",
  emotional_colour: "chaleur",
  usage_conditions: "courant",
  notable_use: "",
  lyric: "",
};

async function generateMaisons() {
  render(<AddWord onSaved={() => {}} onViewWords={() => {}} />);
  fireEvent.change(screen.getByLabelText("Word"), { target: { value: "maisons" } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: /generate card/i })));
  await screen.findByText("maisons");
}

beforeEach(() => {
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, String(v)),
  });
  fake.invoke.mockReset().mockResolvedValue({ data: generated, error: null });
  fake.rpc.mockReset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("saving a word from the shared cache", () => {
  it("adds the shared card for this user and sends only their edits as personal notes", async () => {
    fake.rpc.mockResolvedValue({ data: 1, error: null });
    await generateMaisons();

    fireEvent.change(screen.getByLabelText("Definition"), { target: { value: "Where I live." } });
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /save card/i })));

    expect(fake.rpc).toHaveBeenCalledWith("save_card", {
      p_word_id: "w-maison",
      p_surface_form: "maisons",
      p_user_notes: { definition: "Where I live." },
    });
    expect(await screen.findByRole("heading", { name: "Saved" })).toBeTruthy();
  });

  it("shows the shared dictionary form as text: it can't be edited per user", async () => {
    await generateMaisons();
    expect(screen.queryByLabelText("Dictionary form")).toBeNull();
    expect(screen.getByText("maison")).toBeTruthy();
  });

  it("says so when the word is already in the user's words", async () => {
    fake.rpc.mockResolvedValue({ data: 0, error: null });
    await generateMaisons();

    await act(async () => fireEvent.click(screen.getByRole("button", { name: /save card/i })));

    expect(await screen.findByText(/already in your French words/i)).toBeTruthy();
  });
});
