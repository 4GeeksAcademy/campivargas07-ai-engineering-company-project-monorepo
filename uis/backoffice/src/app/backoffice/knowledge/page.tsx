import { AuthGuard } from "@/components/auth-guard";
import { BackofficeHeader } from "@/components/backoffice-header";
import { KnowledgeAssistant } from "@/components/knowledge/KnowledgeAssistant";

export const metadata = {
  title: "Base de conocimiento — Brasaland Backoffice",
  description: "Consulta autenticada de los manuales oficiales de Brasaland.",
};

export default function BackofficeKnowledgePage() {
  return (
    <AuthGuard>
      <div className="backoffice-page">
        <BackofficeHeader activeView="knowledge" badge="Manuales oficiales" />
        <main className="container bo-main"><KnowledgeAssistant /></main>
      </div>
    </AuthGuard>
  );
}
