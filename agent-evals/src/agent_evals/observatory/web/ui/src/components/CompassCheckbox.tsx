import { type KeyboardEvent } from "react";

interface CompassCheckboxProps {
  checked: boolean;
  onChange?: (checked: boolean) => void;
  className?: string;
  "aria-label"?: string;
}

export function CompassCheckbox({
  checked,
  onChange,
  className = "",
  "aria-label": ariaLabel = "Select",
}: CompassCheckboxProps) {
  const handleClick = () => onChange?.(!checked);

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onChange?.(!checked);
    }
  };

  return (
    <div
      role="checkbox"
      aria-checked={checked}
      aria-label={ariaLabel}
      tabIndex={0}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={`w-5 h-5 inline-flex items-center justify-center cursor-pointer${
        checked ? " compass-checkbox-checked" : ""
      }${className ? ` ${className}` : ""}`}
    >
      <svg viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" className="w-5 h-5">
        <circle
          cx="10"
          cy="10"
          r="9"
          stroke="#E5E5E5"
          strokeWidth="2"
          className={`transition-all duration-micro ${
            checked ? "fill-brand-goldenrod stroke-brand-goldenrod" : "fill-transparent"
          }`}
        />
        <path
          d="M6 10.5L8.5 13L14 7"
          stroke="#FFFFFF"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
          className={checked ? "compass-checkmark-draw" : "compass-checkmark-hidden"}
        />
      </svg>

    </div>
  );
}
