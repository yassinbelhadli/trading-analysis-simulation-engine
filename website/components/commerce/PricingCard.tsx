import Card from "@/components/primitives/Card";
import Icon from "@/components/primitives/Icon";
import LinkButton from "@/components/primitives/LinkButton";

type PricingCardProps = {
  name: string;
  price: string;
  billingLabel: string;
  accountLimit: string;
  features: string[];
  href: string;
  featured?: boolean;
  available?: boolean;
};

export default function PricingCard({
  name,
  price,
  billingLabel,
  accountLimit,
  features,
  href,
  featured = false,
  available = true,
}: PricingCardProps) {
  return (
    <Card elevated={featured} className={featured ? "pricing-card pricing-card--featured" : "pricing-card"}>
      <p className="eyebrow">{featured ? "Recommended" : "Plan"}</p>
      <h2 className="feature-card__title">{name}</h2>
      <p className="pricing-card__price">{price}</p>
      <p className="pricing-card__billing">{billingLabel}</p>
      <p className="pricing-card__limit">{accountLimit}</p>
      <ul className="pricing-card__features">
        {features.map((feature) => <li key={feature}><Icon name="check" size={16} />{feature}</li>)}
      </ul>
      <LinkButton href={href} variant={featured ? "primary" : "secondary"} className="pricing-card__action">
        {available ? `Choose ${name}` : "Contact support"}
      </LinkButton>
    </Card>
  );
}
