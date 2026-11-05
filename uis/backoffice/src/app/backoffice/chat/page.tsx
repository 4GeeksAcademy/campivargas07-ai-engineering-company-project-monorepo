import { AuthGuard } from '@/components/auth-guard';
import { BackofficeHeader } from '@/components/backoffice-header';
import { ChatAssistant } from '@/components/chat/ChatAssistant';

export default function ChatPage() {
  return (
    <AuthGuard>
      <div className="backoffice-page">
        <BackofficeHeader activeView="chat" badge="Chat en tiempo real" />
        <main className="container bo-main">
          <ChatAssistant />
        </main>
      </div>
    </AuthGuard>
  );
}