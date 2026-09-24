/**
 * Model-processing consent screen (us-4 item 5): a separate, explicit screen
 * — uploads of model-eligible documents and profile drafting stay refused
 * until the user grants it here. Withdrawal happens from the same screen
 * once granted.
 */

import { Button } from '@/components/ui/button';

const MODEL_PROCESSING_TEXT =
  'Allow document processing by the model? Your eligible documents (CV, motivation letter) are sent to the AI provider to draft your applicant profile. Ineligible documents are stored encrypted and never leave the server. You can withdraw this consent at any time.';

interface ConsentScreenProps {
  granted: boolean;
  granting: boolean;
  error: string | null;
  onGrant: () => void;
  onWithdraw: () => void;
}

export function ConsentScreen({
  granted,
  granting,
  error,
  onGrant,
  onWithdraw,
}: ConsentScreenProps) {
  return (
    <section
      aria-label="Model-processing consent"
      className="rounded-md border border-foreground/10 bg-card p-4"
    >
      <p className="text-xs/relaxed text-card-foreground">
        {MODEL_PROCESSING_TEXT}
      </p>
      {error ? (
        <p role="alert" className="mt-2 text-xs text-red-600">
          {error}
        </p>
      ) : null}
      <div className="mt-3">
        {granted ? (
          <Button type="button" variant="outline" onClick={onWithdraw}>
            Withdraw consent
          </Button>
        ) : (
          <Button type="button" disabled={granting} onClick={onGrant}>
            {granting ? 'Granting…' : 'Allow model processing'}
          </Button>
        )}
      </div>
    </section>
  );
}
