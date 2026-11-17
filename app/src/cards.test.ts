import { describe, expect, it } from "vitest";
import { toWordList, userEdits, type UserCardRow } from "./cards";

const row = (over: Partial<UserCardRow> = {}): UserCardRow => ({
  card_id: "c1",
  surface_form: "maisons",
  created_at: "2026-11-17T10:00:00Z",
  cards: {
    words: {
      id: "w1",
      language: "French",
      lemma: "maison",
      notes: [
        { kind: "definition", body: "Bâtiment d'habitation." },
        { kind: "register", body: "Casual" },
      ],
      user_notes: [],
    },
  },
  ...over,
});

describe("toWordList", () => {
  it("flattens a user_cards row into a word with its shared notes", () => {
    expect(toWordList([row()])).toEqual([
      {
        id: "w1",
        surface_form: "maisons",
        lemma: "maison",
        language: "French",
        created_at: "2026-11-17T10:00:00Z",
        notes: [
          { kind: "definition", body: "Bâtiment d'habitation." },
          { kind: "register", body: "Casual" },
        ],
      },
    ]);
  });

  it("shows the user's own note instead of the shared one of the same kind", () => {
    const r = row();
    r.cards.words.user_notes = [{ kind: "definition", body: "My own definition" }];

    const [word] = toWordList([r]);

    expect(word.notes).toContainEqual({ kind: "definition", body: "My own definition" });
    expect(word.notes).not.toContainEqual({ kind: "definition", body: "Bâtiment d'habitation." });
    expect(word.notes).toContainEqual({ kind: "register", body: "Casual" });
  });

  it("lists a word once even if the user studies several of its cards", () => {
    expect(toWordList([row(), row()])).toHaveLength(1);
  });
});

describe("userEdits", () => {
  const generated = { definition: "Bâtiment.", example: "Ma maison.", register: "Casual" };

  it("returns only the fields the user changed, as personal notes", () => {
    expect(userEdits(generated, { ...generated, definition: "  Where I live. " })).toEqual({
      definition: "Where I live.",
    });
  });

  it("returns nothing when the user changed nothing", () => {
    expect(userEdits(generated, { ...generated })).toEqual({});
  });

  it("ignores a field the user cleared, so the shared note still shows", () => {
    expect(userEdits(generated, { ...generated, example: "   " })).toEqual({});
  });
});
