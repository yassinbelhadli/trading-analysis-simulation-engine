import Link from "next/link";
import Image from "next/image";

type LogoProps = {
  compact?: boolean;
};

export default function Logo({ compact = false }: LogoProps) {
  return (
    <Link className="logo" href="/" aria-label="ICT Funded EA Pro — Home">
      <span className="logo__chip" aria-hidden="true">
        <Image src="/logo.png" alt="" width={634} height={410} priority className="logo__image" />
      </span>
      {!compact && <span className="logo__wordmark">ICT Funded EA Pro</span>}
    </Link>
  );
}
