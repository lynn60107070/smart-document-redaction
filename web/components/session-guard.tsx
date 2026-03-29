"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { useSession } from "../lib/session";

export function SessionGuard({
  children,
  requireResult = false,
}: {
  children: React.ReactNode;
  requireResult?: boolean;
}) {
  const router = useRouter();
  const { loading, session } = useSession();

  useEffect(() => {
    if (loading) {
      return;
    }
    if (!session) {
      router.replace("/");
      return;
    }
    if (requireResult && !session.result) {
      router.replace("/review");
    }
  }, [loading, requireResult, router, session]);

  if (loading || !session || (requireResult && !session.result)) {
    return null;
  }

  return <>{children}</>;
}
