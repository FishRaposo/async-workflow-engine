export function RunListSkeleton() {
  return (
    <div data-testid="run-list-skeleton" className="space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div
          key={i}
          className="flex animate-pulse items-center justify-between rounded-lg border border-gray-200 bg-white p-4"
        >
          <div className="space-y-2">
            <div className="h-4 w-48 rounded bg-gray-200" />
            <div className="h-3 w-32 rounded bg-gray-100" />
          </div>
          <div className="h-5 w-20 rounded-full bg-gray-100" />
        </div>
      ))}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className="card animate-pulse">
      <div className="space-y-3">
        <div className="h-4 w-1/3 rounded bg-gray-200" />
        <div className="h-3 w-full rounded bg-gray-100" />
        <div className="h-3 w-2/3 rounded bg-gray-100" />
      </div>
    </div>
  );
}

export function DagSkeleton() {
  return (
    <div className="card flex h-64 animate-pulse items-center justify-center">
      <div className="h-32 w-3/4 rounded bg-gray-100" />
    </div>
  );
}

export function TableSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-12 w-full animate-pulse rounded-lg border border-gray-200 bg-white"
        />
      ))}
    </div>
  );
}
