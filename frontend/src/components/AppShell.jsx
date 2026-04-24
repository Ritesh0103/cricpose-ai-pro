import Navbar from "@/components/Navbar";

export default function AppShell({ title, description, children, eyebrow }) {
  return (
    <div className="min-h-screen">
      <Navbar />
      <main className="page-shell mt-6">
        <header className="mb-6">
          {eyebrow ? <div className="eyebrow mb-2">{eyebrow}</div> : null}
          <h1 className="text-3xl md:text-5xl font-semibold tracking-tight" data-testid="page-title">
            {title}
          </h1>
          {description ? (
            <p className="muted mt-3 text-base max-w-2xl">{description}</p>
          ) : null}
        </header>
        <div className="flex flex-col gap-5">{children}</div>
      </main>
    </div>
  );
}
