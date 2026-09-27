import type { IconName } from "@/components/primitives/Icon";
import Icon from "@/components/primitives/Icon";
import Card from "@/components/primitives/Card";

type FeatureCardProps = {
  icon: IconName;
  title: string;
  description: string;
};

export default function FeatureCard({ icon, title, description }: FeatureCardProps) {
  return (
    <Card interactive>
      <div className="feature-card__icon"><Icon name={icon} size={20} /></div>
      <h2 className="feature-card__title">{title}</h2>
      <p className="feature-card__description">{description}</p>
    </Card>
  );
}
