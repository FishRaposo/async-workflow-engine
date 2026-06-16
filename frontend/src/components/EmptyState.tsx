import type { LucideIcon } from "lucide-react";
import { Inbox } from "lucide-react";

interface Props {
  title: string;
  message?: string;
  icon?: LucideIcon;
  action?: React.ReactNode;
}

export default function EmptyState({ title, message, icon: Icon = Inbox, action }: Props) {
  return (
    <div
      data-testid="empty-state"
      className="flex flex-col items-center justify-center rounded-lg border border-dashed border-gray-300 bg-white px-6 py-12 text-center"
    >
      <Icon className="mb-3 h-9 w-9 text-gray-300" />
      <h3 className="text-sm font-semibold text-gray-700">{title}</h3>
      {message && <p className="mt-1 max-w-sm text-sm text-gray-500">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
