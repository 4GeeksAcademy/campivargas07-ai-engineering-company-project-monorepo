import { AuthGuard } from '@/components/auth-guard';
import { BackofficeHeader } from '@/components/backoffice-header';
import { RfpIntake } from '@/components/rfp-intake/RfpIntake';

export default function RfpIntakePage() {
  return <AuthGuard>
    <div className="backoffice-page">
      <BackofficeHeader activeView="knowledge" badge="RFP Intake" />
      <main className="container bo-main"><RfpIntake /></main>
    </div>
  </AuthGuard>;
}
