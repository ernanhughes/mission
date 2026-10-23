import type { ReactNode } from "react";
import { AlertTriangle, CircleSlash, Loader2, RefreshCw } from "lucide-react";
import type { ActionState, ApplicationStatus } from "../types/api";
import { provenanceLabel, titleCase } from "../lib/format";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header">
      <div className="page-heading">
        {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
        <h1>{title}</h1>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </header>
  );
}

export function Section({
  title,
  description,
  actions,
  children,
  className = "",
  id,
}: {
  title?: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <section className={`section ${className}`} id={id}>
      {title ? (
        <header className="section-header">
          <div>
            <h2>{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>
          {actions ? <div className="section-actions">{actions}</div> : null}
        </header>
      ) : null}
      {children}
    </section>
  );
}

export function StatusDot({ state }: { state: string }) {
  return <span className={`status-dot status-${state}`} aria-hidden="true" />;
}

export function StatusBadge({ status }: { status: ApplicationStatus }) {
  return (
    <span className={`status-badge status-${status.state}`} title={status.detail}>
      <StatusDot state={status.state} />
      {status.label}
      {status.ownership === "external" ? <span className="status-note">external</span> : null}
    </span>
  );
}

export function SimpleStatusBadge({ state, label }: { state: string; label?: string }) {
  return (
    <span className={`status-badge status-${state}`}>
      <StatusDot state={state} />
      {label ?? titleCase(state)}
    </span>
  );
}

export function ProvenanceBadge({ value }: { value: string }) {
  return <span className={`provenance provenance-${value}`}>{provenanceLabel(value)}</span>;
}

export function Tag({ children, tone = "default" }: { children: ReactNode; tone?: string }) {
  return <span className={`tag tag-${tone}`}>{children}</span>;
}

export function ActionButton({
  action,
  onClick,
  children,
  variant = "secondary",
  icon,
  type = "button",
  small = false,
  title,
}: {
  action?: ActionState;
  onClick: () => void;
  children: ReactNode;
  variant?: "primary" | "secondary" | "danger" | "ghost";
  icon?: ReactNode;
  type?: "button" | "submit";
  small?: boolean;
  title?: string;
}) {
  const disabled = action ? !action.enabled : false;
  return (
    <button
      type={type}
      className={`button button-${variant} ${small ? "button-small" : ""}`}
      onClick={onClick}
      disabled={disabled}
      title={disabled ? action?.reason ?? title : title}
    >
      {icon}
      {children}
    </button>
  );
}

export function DisabledReasons({ actions }: { actions: Array<[string, ActionState]> }) {
  const disabled = actions.filter(([, action]) => !action.enabled && action.reason);
  if (!disabled.length) return null;
  return (
    <details className="action-reasons">
      <summary>Why some actions are unavailable</summary>
      <ul>
        {disabled.map(([name, action]) => (
          <li key={name}>
            <strong>{name}</strong> {action.reason}
          </li>
        ))}
      </ul>
    </details>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon ?? <CircleSlash size={20} />}</div>
      <h3>{title}</h3>
      {description ? <p>{description}</p> : null}
      {action ? <div className="empty-action">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <AlertTriangle size={20} />
      <div>
        <strong>Could not load this view</strong>
        <p>{message}</p>
      </div>
      {onRetry ? (
        <button className="button button-secondary button-small" onClick={onRetry}>
          <RefreshCw size={14} /> Retry
        </button>
      ) : null}
    </div>
  );
}

export function InlineError({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="inline-error" role="alert">
      <AlertTriangle size={15} />
      <span>{message}</span>
    </div>
  );
}

export function LoadingBlock({ label = "Loading", compact = false }: { label?: string; compact?: boolean }) {
  return (
    <div className={`loading-block ${compact ? "loading-compact" : ""}`} role="status">
      <Loader2 size={18} className="spin" />
      <span>{label}</span>
    </div>
  );
}

export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div className="skeleton-card" aria-hidden="true">
      <div className="skeleton skeleton-title" />
      {Array.from({ length: lines }).map((_, index) => (
        <div className={`skeleton skeleton-line ${index === lines - 1 ? "short" : ""}`} key={index} />
      ))}
    </div>
  );
}

export function Stat({ label, value, detail }: { label: string; value: ReactNode; detail?: string }) {
  return (
    <div className="stat">
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      {detail ? <span className="stat-detail">{detail}</span> : null}
    </div>
  );
}

export function PathText({ children }: { children: ReactNode }) {
  return <code className="path-text">{children}</code>;
}

export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="key-value">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}
