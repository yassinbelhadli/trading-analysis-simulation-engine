type PageHeroProps = {
  eyebrow?: string;
  title: string;
  description?: string;
  align?: "left" | "center";
};

export default function PageHero({ eyebrow, title, description, align = "left" }: PageHeroProps) {
  return (
    <div className={`page-hero ${align === "center" ? "page-hero--center" : ""}`}>
      <div className="container">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="page-hero__title">{title}</h1>
        {description && <p className="page-hero__description">{description}</p>}
      </div>
    </div>
  );
}
