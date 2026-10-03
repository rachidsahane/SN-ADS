import { setupServer } from "msw/node";

/** Serveur MSW partagé : l'API est toujours simulée en test unitaire (TESTING.md section 2). */
export const server = setupServer();
