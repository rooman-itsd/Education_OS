/**
 * A small switch between views, e.g. Bars / Trend or All / Urgent / Pending. A group of toggle buttons
 * (aria-pressed), not tabs: it switches a view in place and has no tab panels to point at.
 */
export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="eos-segmented" role="group" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={v} type="button" aria-pressed={value === v} className="eos-segmented__option" onClick={() => onChange(v)}>
          {text}
        </button>
      ))}
    </div>
  );
}
