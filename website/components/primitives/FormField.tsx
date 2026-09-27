import type { InputHTMLAttributes, TextareaHTMLAttributes } from "react";

type FieldProps = {
  id: string;
  label: string;
  hint?: string;
  error?: string;
};

type TextFieldProps = FieldProps & InputHTMLAttributes<HTMLInputElement>;

export function TextField({ id, label, hint, error, ...props }: TextFieldProps) {
  const descriptionId = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <label className="form-field" htmlFor={id}>
      <span className="form-field__label">{label}</span>
      <input
        id={id}
        className="form-field__control"
        aria-describedby={descriptionId}
        aria-invalid={Boolean(error)}
        {...props}
      />
      {error && <span className="form-field__hint" id={`${id}-error`} role="alert">{error}</span>}
      {!error && hint && <span className="form-field__hint" id={`${id}-hint`}>{hint}</span>}
    </label>
  );
}

type TextAreaFieldProps = FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>;

export function TextAreaField({ id, label, hint, error, ...props }: TextAreaFieldProps) {
  const descriptionId = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <label className="form-field" htmlFor={id}>
      <span className="form-field__label">{label}</span>
      <textarea
        id={id}
        className="form-field__control"
        aria-describedby={descriptionId}
        aria-invalid={Boolean(error)}
        {...props}
      />
      {error && <span className="form-field__hint" id={`${id}-error`} role="alert">{error}</span>}
      {!error && hint && <span className="form-field__hint" id={`${id}-hint`}>{hint}</span>}
    </label>
  );
}
