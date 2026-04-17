export default function ErrorState({ message }) {
  return (
    <section className="panel error-panel">
      <h2>Unable to load data</h2>
      <p>{message}</p>
      <p>
        Check your API URLs, CORS configuration, and deployed endpoint
        responses.
      </p>
    </section>
  );
}