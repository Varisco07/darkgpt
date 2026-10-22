import { redirect } from "next/navigation";

/** La dashboard parte dalla panoramica. */
export default function HomePage() {
  redirect("/overview");
}
