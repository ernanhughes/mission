import { BooksCollectionPage } from "./BooksPage";

export function FictionBooksPage() {
  return (
    <BooksCollectionPage
      apiBase="/api/fiction-books"
      eyebrow="Fiction and publishing"
      title="Fiction Books"
      description="Fiction manuscripts stay independent from technical books. Every detected project under the fiction root is added as a first-class workspace with the same status, progress and review controls."
      emptyHint={
        "Add a fiction manuscript at " +
        "C:\\fiction-books\\<project>\\chapters, then use Detect books. " +
        "Only projects with chapter files are listed; research notes and tooling are excluded."
      }
    />
  );
}
