export default function Loading() {
  return (
    <div className="page-hero page-hero--center">
      <div className="container">
        <p className="eyebrow">Loading</p>
        <h1 className="page-hero__title">Preparing the page…</h1>
        <p className="page-hero__description" aria-busy="true">
          Please wait a moment.
        </p>
      </div>
    </div>
  );
}
