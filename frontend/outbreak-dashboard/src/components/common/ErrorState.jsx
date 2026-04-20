export default function ErrorState({ message }) {
  return (
    <section className="error-panel">
      <h2>Unable to load dashboard data</h2>
      <p>{message}</p>
      <p>
        Check your deployed API URLs, CORS settings, and live endpoint responses.
      </p>
    </section>
  );
}