import { useReducer, useCallback } from "react";

export type ViewMode = "table" | "cards";
export type PanelTab = "overview" | "providers" | "history";

export interface ModelsState {
  selectedModelIds: Set<string>;
  selectedModelId: string | null;
  viewMode: ViewMode;
  panelTab: PanelTab;
  selectedProviders: Set<string>;
  showMobileFilters: boolean;
  showHint: boolean;
  cardLimit: number;
  searchTerm: string;
}

type Action =
  | { type: "TOGGLE_ROW"; id: string }
  | { type: "SELECT_ALL"; ids: string[] }
  | { type: "CLEAR_SELECTION" }
  | { type: "OPEN_DETAIL"; id: string }
  | { type: "CLOSE_DETAIL" }
  | { type: "SET_VIEW_MODE"; mode: ViewMode }
  | { type: "SET_PANEL_TAB"; tab: PanelTab }
  | { type: "SET_PROVIDERS"; providers: Set<string> }
  | { type: "SET_MOBILE_FILTERS"; open: boolean }
  | { type: "DISMISS_HINT" }
  | { type: "SET_SEARCH_TERM"; term: string }
  | { type: "LOAD_MORE_CARDS" }
  | { type: "RESET_CARD_LIMIT" }
  | { type: "CLEAR_ALL_FILTERS" };

function createInitialState(search: string): ModelsState {
  return {
    selectedModelIds: new Set(),
    selectedModelId: null,
    viewMode: "table",
    panelTab: "overview",
    selectedProviders: new Set(),
    showMobileFilters: false,
    showHint: true,
    cardLimit: 24,
    searchTerm: search,
  };
}

function reducer(state: ModelsState, action: Action): ModelsState {
  switch (action.type) {
    case "TOGGLE_ROW": {
      const next = new Set(state.selectedModelIds);
      if (next.has(action.id)) {
        next.delete(action.id);
      } else {
        next.add(action.id);
      }
      return { ...state, selectedModelIds: next };
    }
    case "SELECT_ALL":
      return {
        ...state,
        selectedModelIds:
          action.ids.length === 0 ? new Set() : new Set(action.ids),
      };
    case "CLEAR_SELECTION":
      return { ...state, selectedModelIds: new Set() };
    case "OPEN_DETAIL":
      return { ...state, selectedModelId: action.id, panelTab: "overview" };
    case "CLOSE_DETAIL":
      return { ...state, selectedModelId: null };
    case "SET_VIEW_MODE":
      return { ...state, viewMode: action.mode };
    case "SET_PANEL_TAB":
      return { ...state, panelTab: action.tab };
    case "SET_PROVIDERS":
      return { ...state, selectedProviders: action.providers };
    case "SET_MOBILE_FILTERS":
      return { ...state, showMobileFilters: action.open };
    case "DISMISS_HINT":
      return state.showHint ? { ...state, showHint: false } : state;
    case "SET_SEARCH_TERM":
      return { ...state, searchTerm: action.term };
    case "LOAD_MORE_CARDS":
      return { ...state, cardLimit: state.cardLimit + 24 };
    case "RESET_CARD_LIMIT":
      return state.cardLimit === 24 ? state : { ...state, cardLimit: 24 };
    case "CLEAR_ALL_FILTERS":
      return {
        ...state,
        searchTerm: "",
        selectedProviders: new Set(),
      };
    default:
      return state;
  }
}

export function useModelsReducer(initialSearch: string) {
  const [state, dispatch] = useReducer(
    reducer,
    initialSearch,
    createInitialState,
  );

  const toggleRow = useCallback(
    (id: string) => dispatch({ type: "TOGGLE_ROW", id }),
    [],
  );
  const selectAll = useCallback(
    (ids: string[]) => dispatch({ type: "SELECT_ALL", ids }),
    [],
  );
  const clearSelection = useCallback(
    () => dispatch({ type: "CLEAR_SELECTION" }),
    [],
  );
  const openDetail = useCallback(
    (id: string) => dispatch({ type: "OPEN_DETAIL", id }),
    [],
  );
  const closeDetail = useCallback(
    () => dispatch({ type: "CLOSE_DETAIL" }),
    [],
  );

  return { state, dispatch, toggleRow, selectAll, clearSelection, openDetail, closeDetail };
}
