import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { Icons } from "@eos/ui-kit";

export interface ListboxOption {
  value: string;
  label: string;
  /** Optional secondary text shown on the right of the option (e.g. a count). */
  hint?: string;
}

/**
 * A styled single-select dropdown (WAI-ARIA "select-only combobox" pattern): a button that shows the
 * current choice and opens a listbox of options. Keyboard: Enter/Space/ArrowDown/ArrowUp open it;
 * inside, ArrowUp/ArrowDown/Home/End move, typing a letter jumps to the next match, Enter/Space choose,
 * Escape or Tab close. Clicking outside closes it. Used instead of the browser's native select so the
 * control matches the site, without losing keyboard or screen-reader behaviour.
 */
export function Listbox({
  label,
  value,
  options,
  onChange,
  className,
  hideLabel = false,
}: {
  label: string;
  value: string;
  options: ListboxOption[];
  onChange: (value: string) => void;
  className?: string;
  hideLabel?: boolean;
}) {
  const id = useId();
  const labelId = `${id}-label`;
  const buttonId = `${id}-button`;
  const listId = `${id}-list`;
  const rootRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const [open, setOpen] = useState(false);
  const selectedIndex = Math.max(
    0,
    options.findIndex((o) => o.value === value),
  );
  const [active, setActive] = useState(selectedIndex);
  const current = options[selectedIndex];

  // Close on a click outside.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: PointerEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [open]);

  // Focus the list when it opens and keep the active option in view.
  useEffect(() => {
    if (!open) return;
    listRef.current?.focus({ preventScroll: true });
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.querySelector<HTMLElement>(`[data-index="${active}"]`);
    el?.scrollIntoView({ block: "nearest" });
  }, [open, active]);

  const openAt = (index: number) => {
    setActive(index);
    setOpen(true);
  };
  const choose = (index: number) => {
    const option = options[index];
    if (option) onChange(option.value);
    setOpen(false);
    buttonRef.current?.focus();
  };

  const onButtonKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      openAt(selectedIndex);
    }
  };

  const onListKey = (e: KeyboardEvent<HTMLUListElement>) => {
    const last = options.length - 1;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActive((a) => Math.min(last, a + 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActive((a) => Math.max(0, a - 1));
        break;
      case "Home":
        e.preventDefault();
        setActive(0);
        break;
      case "End":
        e.preventDefault();
        setActive(last);
        break;
      case "Enter":
      case " ":
        e.preventDefault();
        choose(active);
        break;
      case "Escape":
        e.preventDefault();
        setOpen(false);
        buttonRef.current?.focus();
        break;
      case "Tab":
        setOpen(false);
        break;
      default:
        if (e.key.length === 1 && /\S/.test(e.key)) {
          const key = e.key.toLowerCase();
          for (let step = 1; step <= options.length; step++) {
            const i = (active + step) % options.length;
            if (options[i]?.label.toLowerCase().startsWith(key)) {
              setActive(i);
              break;
            }
          }
        }
    }
  };

  return (
    <div ref={rootRef} className={["wpc-lb", open ? "is-open" : "", className].filter(Boolean).join(" ")}>
      <span id={labelId} className={hideLabel ? "eos-sr-only" : "wpc-lb__label"}>
        {label}
      </span>
      <button
        ref={buttonRef}
        id={buttonId}
        type="button"
        className="wpc-lb__button"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-labelledby={`${labelId} ${buttonId}`}
        onClick={() => (open ? setOpen(false) : openAt(selectedIndex))}
        onKeyDown={onButtonKey}
      >
        <span className="wpc-lb__value">{current?.label}</span>
        {current?.hint && <span className="wpc-lb__hint">{current.hint}</span>}
        <Icons.ChevronDown size={18} aria-hidden className="wpc-lb__chevron" />
      </button>
      {open && (
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          tabIndex={-1}
          aria-labelledby={labelId}
          aria-activedescendant={`${id}-opt-${active}`}
          className="wpc-lb__list"
          onKeyDown={onListKey}
        >
          {options.map((o, i) => (
            <li
              key={o.value}
              id={`${id}-opt-${i}`}
              role="option"
              data-index={i}
              aria-selected={o.value === value}
              className={i === active ? "wpc-lb__option is-active" : "wpc-lb__option"}
              onPointerMove={() => setActive(i)}
              onClick={() => choose(i)}
            >
              <span className="wpc-lb__option-label">{o.label}</span>
              {o.hint && <span className="wpc-lb__option-hint">{o.hint}</span>}
              {o.value === value && <Icons.Check size={16} aria-hidden className="wpc-lb__tick" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
