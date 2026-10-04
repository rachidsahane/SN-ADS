"use client";

import { useEffect } from "react";

import { labels } from "@/lib/labels";
import { useToast } from "@/providers/toast-provider";

/** Avis « pas d'accès » (prototype : message bref) quand l'espace d'administration a renvoyé un marketer ici (PRD CL-08). */
export function ForbiddenToast() {
  const { toast } = useToast();
  useEffect(() => {
    toast(labels.errors.noAccess);
  }, [toast]);
  return null;
}
