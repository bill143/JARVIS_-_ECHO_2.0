import { Button } from "@/components/ui";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="font-mono text-5xl font-bold text-accent">404</p>
      <h1 className="mt-4 text-2xl font-bold text-text">Page not found</h1>
      <p className="mt-2 max-w-md text-muted">
        The page you&apos;re looking for doesn&apos;t exist or may have moved.
      </p>
      <div className="mt-6">
        <Button href="/">Back to Best 10</Button>
      </div>
    </div>
  );
}
