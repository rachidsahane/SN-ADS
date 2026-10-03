import { redirect } from "next/navigation";

/** « / » mène à la page de prédiction. */
export default function HomePage(): never {
  redirect("/predict");
}
