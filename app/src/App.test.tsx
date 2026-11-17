// @vitest-environment jsdom
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// --- A fake Supabase client: one signed-in user at a time, controllable word lists ---
type Row = { id: string; surface_form: string; lemma: string; language: string; created_at: string; notes: [] };
type Result = { data: Row[] | null; error: null };

const fake = vi.hoisted(() => {
  const state = {
    authCallback: null as null | ((event: string, session: unknown) => void),
    initialSession: null as unknown,
    // Each call to from("words") gets the next pending response; the test resolves them.
    pending: [] as { resolve: (r: Result) => void }[],
  };
  const supabase = {
    auth: {
      getSession: () => Promise.resolve({ data: { session: state.initialSession } }),
      onAuthStateChange: (cb: (event: string, session: unknown) => void) => {
        state.authCallback = cb;
        return { data: { subscription: { unsubscribe: () => {} } } };
      },
      signOut: () => Promise.resolve({ error: null }),
    },
    // Every query-builder step returns the builder; awaiting it waits for the test to respond.
    from: () => {
      const result = new Promise<Result>((resolve) => state.pending.push({ resolve }));
      const builder: Record<string, unknown> = {
        then: (ok: (r: Result) => unknown, fail?: (e: unknown) => unknown) => result.then(ok, fail),
      };
      for (const step of ["select", "order", "limit", "or"]) builder[step] = () => builder;
      return builder;
    },
  };
  return { state, supabase };
});

vi.mock("./supabase", async (importActual) => ({
  ...(await importActual<typeof import("./supabase")>()),
  configError: null,
  supabase: fake.supabase,
}));

import App from "./App";

const session = (id: string) => ({ user: { id }, access_token: `token-${id}` });
const word = (surface_form: string): Row => ({
  id: surface_form, surface_form, lemma: surface_form, language: "French",
  created_at: "2026-11-16T00:00:00Z", notes: [],
});
const respond = (index: number, rows: Row[]) =>
  act(async () => fake.state.pending[index].resolve({ data: rows, error: null }));
const switchUser = (id: string) =>
  act(async () => fake.state.authCallback?.("SIGNED_IN", session(id)));

beforeEach(() => {
  // Node 25's built-in localStorage shadows jsdom's; give the app a plain in-memory one.
  const store = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, String(v)),
    removeItem: (k: string) => void store.delete(k),
    clear: () => store.clear(),
  });
  fake.state.pending = [];
  fake.state.authCallback = null;
  fake.state.initialSession = session("user-a");
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("switching between signed-in users", () => {
  it("replaces the previous user's words with the new user's words", async () => {
    render(<App />);
    await waitFor(() => expect(fake.state.pending).toHaveLength(1));
    await respond(0, [word("maison")]);
    expect(await screen.findByText("maison")).toBeTruthy();

    await switchUser("user-b");

    await waitFor(() => expect(fake.state.pending).toHaveLength(2));
    await respond(1, [word("perro")]);
    expect(await screen.findByText("perro")).toBeTruthy();
    expect(screen.queryByText("maison")).toBeNull();
  });

  it("ignores the previous user's response if it arrives after the switch", async () => {
    render(<App />);
    await waitFor(() => expect(fake.state.pending).toHaveLength(1));

    await switchUser("user-b"); // user A's request is still in flight

    await waitFor(() => expect(fake.state.pending).toHaveLength(2));
    await respond(1, [word("perro")]);
    await respond(0, [word("maison")]); // stale response from user A lands last

    expect(await screen.findByText("perro")).toBeTruthy();
    expect(screen.queryByText("maison")).toBeNull();
  });
});
