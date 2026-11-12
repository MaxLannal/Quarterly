interface PlaceholderProps {
  title: string;
  route: string;
  prompt: string;
}

export function Placeholder({ title, route, prompt }: PlaceholderProps) {
  return (
    <section className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-semibold">{title}</h1>
      <p className="mt-2 text-muted-foreground">
        Placeholder for <code>{route}</code>. Built in prompt {prompt}.
      </p>
    </section>
  );
}
