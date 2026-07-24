import { useEffect } from "react";

interface SideDrawerProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}

export function SideDrawer({
  open,
  title,
  onClose,
  children,
}: SideDrawerProps) {
  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div
      className="side-drawer-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <aside
        className="side-drawer"
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <header className="side-drawer-header">
          <h2>{title}</h2>
          <button type="button" onClick={onClose} aria-label={`关闭${title}`}>
            ×
          </button>
        </header>
        <div className="side-drawer-content">{children}</div>
      </aside>
    </div>
  );
}
