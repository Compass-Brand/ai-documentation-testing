export const TRANSITIONS = {
  micro: "transition-all duration-[150ms] ease-out",       // hover, focus
  state: "transition-all duration-[250ms] ease-in-out",    // tab switch, select
  page: "transition-all duration-[350ms] ease-in-out",     // route change
  modal: "transition-all duration-[250ms] ease-out",       // panel open
} as const;
