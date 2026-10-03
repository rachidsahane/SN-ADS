let queue: Promise<unknown> = Promise.resolve();

/**
 * Verrou de session du client navigateur : exécute les opérations d'authentification une par une, dans l'onglet.
 *
 * Le verrou par défaut de supabase-js (Navigator LockManager) fait échouer le premier rafraîchissement automatique
 * de Firefox (« Acquiring an exclusive Navigator LockManager lock ... immediately failed », erreur non gérée dans la
 * console). Un double rafraîchissement entre onglets reste sans effet : gotrue tolère la réutilisation d'un jeton de
 * rafraîchissement pendant une courte fenêtre (D-077).
 */
export function serialLock<R>(
  _name: string,
  _acquireTimeout: number,
  fn: () => Promise<R>,
): Promise<R> {
  const run = queue.then(fn, fn);
  queue = run.catch(() => undefined);
  return run;
}
