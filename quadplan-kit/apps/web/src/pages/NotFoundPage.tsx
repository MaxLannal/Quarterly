import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <section className="mx-auto max-w-3xl space-y-2 p-6">
      <h1 className="text-2xl font-semibold">Page not found</h1>
      <p>
        <Link to="/" className="text-primary underline">
          Go to the home page
        </Link>
      </p>
    </section>
  );
}
