import type { CardField } from "./cards";

/** One card's fields (#36). A missing field says "Missing"; it is never filled with a default (L8). */
export default function Card({ fields }: { fields: CardField[] }) {
  return (
    <dl className="word-notes">
      {fields.map((f) => (
        <div key={f.key}>
          <dt>{f.label}</dt>
          {f.missing ? <dd className="missing">Missing</dd> : <dd>{f.value}</dd>}
        </div>
      ))}
    </dl>
  );
}
