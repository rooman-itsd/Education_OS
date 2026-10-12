/** A small switch between views, e.g. Bars / Trend or All / Urgent / Pending. */
export function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="eos-segmented" role="tablist" aria-label={label}>
      {options.map(([v, text]) => (
        <button key={v} type="button" role="tab" aria-selected={value === v} className="eos-segmented__option" onClick={() => onChange(v)}>
          {text}
        </button>
      ))}
    </div>
  );
}
