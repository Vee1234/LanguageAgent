import { useState, type FormEvent } from "react";
import { FunctionsHttpError } from "@supabase/supabase-js";
import { CARD_FIELDS, REGISTERS, supabase, type FieldKey, type GeneratedCard } from "./supabase";
import { userEdits } from "./cards";

type Step = "word" | "review" | "saved";

const LANGUAGES = ["French", "Spanish", "German", "Italian", "Portuguese", "Japanese"];

async function errorMessage(err: unknown): Promise<string> {
  // Edge Function errors carry our { error } JSON body; surface it.
  if (err instanceof FunctionsHttpError) {
    try {
      const body = await err.context.json();
      if (body?.error) return body.error;
    } catch { /* fall through */ }
  }
  return err instanceof Error ? err.message : String(err);
}

type Props = { onSaved: () => void; onViewWords: () => void };

export default function AddWord({ onSaved, onViewWords }: Props) {
  const [step, setStep] = useState<Step>("word");
  const [word, setWord] = useState("");
  const [language, setLanguage] = useState(() => localStorage.getItem("language") ?? "French");
  const [card, setCard] = useState<GeneratedCard | null>(null);
  // Shared content as generated; edits are diffed against it and saved as the user's own notes.
  const [original, setOriginal] = useState<GeneratedCard | null>(null);
  const [busy, setBusy] = useState(false);
  const [savedMessage, setSavedMessage] = useState<"new" | "changes" | "already">("new");
  const [error, setError] = useState<string | null>(null);

  async function generate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    localStorage.setItem("language", language);
    const { data, error } = await supabase.functions.invoke<GeneratedCard>("generate-word", {
      body: { word: word.trim(), language },
    });
    setBusy(false);
    if (error || !data) return setError(await errorMessage(error ?? new Error("No response")));
    setCard(data);
    setOriginal(data);
    setStep("review");
  }

  async function save() {
    if (!card || !original) return;
    setBusy(true);
    setError(null);
    const pick = (c: GeneratedCard) => Object.fromEntries(CARD_FIELDS.map(({ key }) => [key, c[key] ?? ""]));
    const edits = userEdits(pick(original), pick(card));
    const { data: added, error } = await supabase.rpc("save_card", {
      p_word_id: card.word_id,
      p_surface_form: card.word,
      p_user_notes: edits,
    });
    setBusy(false);
    if (error) return setError(error.message);
    // Bug 15: 0 means "no new card" (the word was already yours), not failure. The save still
    // succeeded, so always show Saved and refresh the list; only the message depends on the count.
    const changed = Object.keys(edits).length > 0;
    setSavedMessage(
      added !== 0 ? "new" : changed ? "changes" : "already",
    );
    setStep("saved");
    onSaved();
  }

  function startOver() {
    setWord("");
    setCard(null);
    setOriginal(null);
    setError(null);
    setStep("word");
  }

  const edit = (key: FieldKey, value: string) =>
    setCard((c) => (c ? { ...c, [key]: value } : c));

  return (
    <>
      <ol className="steps" aria-label="Progress">
        {(["word", "review", "saved"] as Step[]).map((s, i) => (
          <li key={s} aria-current={s === step ? "step" : undefined}>
            {i + 1}. {s === "word" ? "Word" : s === "review" ? "Card" : "Saved"}
          </li>
        ))}
      </ol>

      {step === "word" && (
        <form className="panel" onSubmit={generate}>
          <h1>Add a word</h1>
          <label>
            Word
            <input autoFocus autoCapitalize="off" autoCorrect="off" spellCheck={false}
              required maxLength={60} value={word} placeholder="e.g. dépaysement"
              onChange={(e) => setWord(e.target.value)} />
          </label>
          <label>
            Language
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
            </select>
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="primary" disabled={busy || !word.trim()}>
            {busy ? "Generating…" : "Generate card"}
          </button>
        </form>
      )}

      {step === "review" && card && (
        <section className="panel">
          <p className="eyebrow">{card.language}</p>
          <h1 className="headword">{card.word}</h1>
          {card.lemma !== card.word && (
            <p className="muted lemma">Dictionary form: <strong>{card.lemma}</strong></p>
          )}

          {CARD_FIELDS.map(({ key, label }) => (
            <label key={key} className="field">
              {label}
              {key === "register" ? (
                <select value={card.register ?? ""} onChange={(e) => edit(key, e.target.value)}>
                  {/* A missing register must look missing (Bug 13): without this option the browser
                      silently shows the first register, as if it had been chosen. */}
                  {!original?.register && <option value="">Not set yet</option>}
                  {REGISTERS.map((r) => <option key={r}>{r}</option>)}
                </select>
              ) : (
                <textarea rows={2} value={card[key] ?? ""} placeholder="None found — add your own"
                  onChange={(e) => edit(key, e.target.value)} />
              )}
            </label>
          ))}

          {error && <p className="error" role="alert">{error}</p>}
          <div className="row">
            <button className="secondary" onClick={startOver} disabled={busy}>Discard</button>
            <button className="primary" onClick={save} disabled={busy}>
              {busy ? "Saving…" : "Save card"}
            </button>
          </div>
        </section>
      )}

      {step === "saved" && card && (
        <section className="panel center">
          <h1>Saved</h1>
          <p>
            {savedMessage === "new" && (
              <><strong>{card.word}</strong> is in your {card.language} words, and its card is due for review now.</>
            )}
            {savedMessage === "changes" && (
              <>Your changes to <strong>{card.word}</strong> are saved. It was already in your {card.language} words.</>
            )}
            {savedMessage === "already" && (
              <><strong>{card.word}</strong> is already in your {card.language} words. Nothing needed saving.</>
            )}
          </p>
          <div className="row">
            <button className="secondary" onClick={onViewWords}>See My words</button>
            <button className="primary" onClick={startOver}>Add another word</button>
          </div>
        </section>
      )}
    </>
  );
}
