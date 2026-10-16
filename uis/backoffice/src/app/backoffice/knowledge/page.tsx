import { AuthGuard } from '@/components/auth-guard';
import { BackofficeHeader } from '@/components/backoffice-header';
import styles from '@/components/knowledge/KnowledgeAssistant.module.css';
import { KnowledgeAssistant } from '@/components/knowledge/KnowledgeAssistant';

export default function KnowledgePage() {
  return <AuthGuard>
    <div className={`backoffice-page ${styles.page}`}>
      <BackofficeHeader activeView="knowledge" badge="Base de conocimiento" />
      <main className="container bo-main"><KnowledgeAssistant /></main>
    </div>
  </AuthGuard>;
}
