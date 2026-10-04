"use client";

import {
  type ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

const HIDE_AFTER_MS = 3200;

type ToastApi = { toast: (message: string) => void };
const ToastContext = createContext<ToastApi>({ toast: () => undefined });

/** Message bref en bas de l'écran (prototype : fond bleu nuit, cadre blueprint, 3,2 s). */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const toast = useCallback((next: string) => {
    setMessage(next);
    if (timer.current) {
      clearTimeout(timer.current);
    }
    timer.current = setTimeout(() => setMessage(null), HIDE_AFTER_MS);
  }, []);

  useEffect(
    () => () => {
      if (timer.current) {
        clearTimeout(timer.current);
      }
    },
    [],
  );

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      {message ? (
        <div
          role="status"
          data-testid="toast"
          className="blueprint fixed bottom-7 left-1/2 z-50 -translate-x-1/2 bg-brand-900 px-[18px] py-[10px] text-sm text-background shadow-md"
        >
          {message}
        </div>
      ) : null}
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  return useContext(ToastContext);
}
