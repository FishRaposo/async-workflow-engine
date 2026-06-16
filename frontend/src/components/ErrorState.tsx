import { AlertCircle } from "lucide-react";

interface Props {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export default function ErrorState({ title = "Couldn't load data", message, onRetry }: Props) {
  return (
    <div
      data-testid="error-state"
      className="flex flex-col items-center justify-center rounded-lg border border-rose-200 bg-rose-50 px-6 py-10 text-center"
    >
      <AlertCircle className="mb-3 h-9 w-9 text-rose-400" />
      <h3 className="text-sm font-semibold text-rose-800">{title}</h3>
      <p className="mt-1 max-w-md text-sm text-rose-600">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-4 rounded-lg bg-rose-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-700"
        >
          Retry
        </button>
      )}
    </div>
  );
}
