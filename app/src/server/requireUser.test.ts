import { describe, expect, it, vi } from "vitest";
import { requireUser } from "../../../supabase/functions/generate-word/logic";

// getUser stands in for supabase.auth.getUser(token): Supabase Auth checks the token and looks the user up.
const realUser = vi.fn(async (token: string) => (token === "user-token" ? { id: "user-1" } : null));

describe("requireUser (Bug 6: only signed-in users may write the shared cache)", () => {
  it("returns the user for a valid signed-in session", async () => {
    await expect(requireUser("Bearer user-token", realUser)).resolves.toEqual({ id: "user-1" });
    expect(realUser).toHaveBeenCalledWith("user-token");
  });

  it("rejects the public anon token: genuine, but it names no user", async () => {
    await expect(requireUser("Bearer public-anon-token", realUser)).resolves.toBeNull();
  });

  it("rejects a missing or malformed Authorization header without asking Supabase", async () => {
    const getUser = vi.fn();
    await expect(requireUser(null, getUser)).resolves.toBeNull();
    await expect(requireUser("Basic abc", getUser)).resolves.toBeNull();
    await expect(requireUser("Bearer ", getUser)).resolves.toBeNull();
    expect(getUser).not.toHaveBeenCalled();
  });

  it("fails closed when Supabase Auth can't be reached", async () => {
    const down = vi.fn(async () => {
      throw new Error("network down");
    });
    await expect(requireUser("Bearer user-token", down)).resolves.toBeNull();
  });
});
