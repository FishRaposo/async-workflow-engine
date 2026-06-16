"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { GitBranch, ListChecks, PlayCircle, Inbox, CalendarClock } from "lucide-react";

const links = [
  { href: "/runs", label: "Runs", icon: ListChecks },
  { href: "/trigger", label: "Trigger", icon: PlayCircle },
  { href: "/dead-letters", label: "Dead Letters", icon: Inbox },
  { href: "/schedules", label: "Schedules", icon: CalendarClock },
];

export default function NavBar() {
  const pathname = usePathname();

  return (
    <header className="border-b border-gray-200 bg-white">
      <nav className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <Link href="/" className="flex items-center gap-2 text-lg font-bold text-brand-700">
          <GitBranch className="h-5 w-5" />
          <span>Flowforge</span>
          <span className="hidden text-xs font-normal text-gray-400 sm:inline">
            workflow console
          </span>
        </Link>
        <div className="flex items-center gap-1">
          {links.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || pathname.startsWith(href + "/");
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                  active
                    ? "bg-brand-50 text-brand-700"
                    : "text-gray-600 hover:bg-gray-50 hover:text-brand-600"
                }`}
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{label}</span>
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
