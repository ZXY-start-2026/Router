import type { ReactNode } from "react";

interface AppLayoutProps {
  sidebar: ReactNode;
  main: ReactNode;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export function AppLayout({ sidebar, main, sidebarOpen, onToggleSidebar }: AppLayoutProps) {
  return (
    <div className={`app-layout ${sidebarOpen ? "sidebar-open" : ""}`}>
      <button
        className="sidebar-toggle"
        type="button"
        aria-label={sidebarOpen ? "收起会话列表" : "展开会话列表"}
        onClick={onToggleSidebar}
      >
        {sidebarOpen ? "收起" : "会话"}
      </button>
      <aside className="sidebar" aria-label="会话列表">
        {sidebar}
      </aside>
      <main className="main-panel">{main}</main>
      {sidebarOpen && (
        <button
          className="sidebar-scrim"
          type="button"
          aria-label="关闭会话列表"
          onClick={onToggleSidebar}
        />
      )}
    </div>
  );
}

