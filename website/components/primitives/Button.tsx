import { forwardRef, type ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "small" | "medium" | "large";
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({
  variant = "primary",
  size = "medium",
  className = "",
  ...props
}, ref) {
  return (
    <button
      ref={ref}
      className={`button button--${variant} button--${size} ${className}`.trim()}
      {...props}
    />
  );
});

export default Button;
