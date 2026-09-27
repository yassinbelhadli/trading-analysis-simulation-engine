import type { ReactNode } from "react";

type LegalPageProps = {
  eyebrow?: string;
  title: string;
  updated: string;
  children: ReactNode;
};

export default function LegalPage({ eyebrow = "Legal", title, updated, children }: LegalPageProps) {
  return (
    <div className="section">
      <div className="container">
        <article className="legal">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="legal__title">{title}</h1>
          <p className="legal__updated">Last updated: {updated}</p>
          <div className="legal__body">{children}</div>
        </article>
      </div>
    </div>
  );
}
