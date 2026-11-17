import { describe, expect, it } from "vitest";
import { PAGE_SIZE, cursorFilter, mergePages, nextCursor } from "./wordsPage";

const w = (card_id: string, created_at: string) => ({ card_id, id: card_id, created_at });

describe("pagination helpers", () => {
  it("uses pages well under the API's 1,000-row cap", () => {
    expect(PAGE_SIZE).toBeLessThanOrEqual(100);
  });

  it("builds a keyset filter on user_cards: strictly older, card_id breaking timestamp ties", () => {
    expect(cursorFilter({ created_at: "2026-11-17T10:00:00Z", card_id: "b" })).toBe(
      'created_at.lt."2026-11-17T10:00:00Z",and(created_at.eq."2026-11-17T10:00:00Z",card_id.lt."b")',
    );
  });

  it("takes the next cursor from the last row of a full page", () => {
    const rows = Array.from({ length: PAGE_SIZE }, (_, i) => w(`id${i}`, `2026-11-17T10:00:${String(59 - (i % 60)).padStart(2, "0")}Z`));
    expect(nextCursor(rows)).toEqual({ card_id: rows.at(-1)!.card_id, created_at: rows.at(-1)!.created_at });
  });

  it("has no next cursor once a page comes back short", () => {
    expect(nextCursor([w("a", "2026-11-17T10:00:00Z")])).toBeNull();
  });

  it("appends a page without duplicating words already shown", () => {
    const merged = mergePages([w("a", "t3"), w("b", "t2")], [w("b", "t2"), w("c", "t1")]);
    expect(merged.map((x) => x.id)).toEqual(["a", "b", "c"]);
  });
});
