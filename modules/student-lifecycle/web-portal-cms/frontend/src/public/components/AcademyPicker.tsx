import type { AcademyType } from "../../api/public-client";

/**
 * The academy package picker: one card per academy type from platform/tenancy GET /academy-types.
 * The academy type is the organisation's academic package (docs/architecture/ARCHITECTURE.md): it is
 * stored on the organisation at registration and approved by the super admin.
 *
 * Built on native radio inputs inside label cards, so it is a real radio group: Tab reaches it, the
 * arrow keys move the choice, and screen readers announce "n of 15, selected". The selected card is
 * marked by a ring and a tick, not by colour alone.
 */
export function AcademyPicker({
  types,
  value,
  onChange,
  name = "academy_type",
  describedBy,
}: {
  types: AcademyType[];
  value: string;
  onChange: (id: string) => void;
  name?: string;
  describedBy?: string;
}) {
  return (
    <div className="wpc-ap" role="radiogroup" aria-labelledby="wpc-ap-label" aria-describedby={describedBy}>
      {types.map((t) => {
        const checked = t.id === value;
        return (
          <label key={t.id} className={checked ? "wpc-ap__card is-selected" : "wpc-ap__card"}>
            <input
              className="wpc-ap__input"
              type="radio"
              name={name}
              value={t.id}
              checked={checked}
              onChange={() => onChange(t.id)}
            />
            <span className="wpc-ap__tick" aria-hidden>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12.5l4.5 4.5L19 7.5" />
              </svg>
            </span>
            <span className="wpc-ap__title">{t.title}</span>
            {t.description && <span className="wpc-ap__desc">{t.description}</span>}
          </label>
        );
      })}
    </div>
  );
}
