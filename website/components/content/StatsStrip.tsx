type Stat = {
  value: string;
  label: string;
};

export default function StatsStrip({ items }: { items: Stat[] }) {
  return (
    <div className="stats-strip" aria-label="Product highlights">
      {items.map((item) => (
        <div className="stats-strip__item" key={item.label}>
          <span className="stats-strip__value">{item.value}</span>
          <span className="stats-strip__label">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
