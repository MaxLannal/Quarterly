import { Link } from "react-router-dom";
import { buttonVariants } from "@/components/ui/button";
import { GlassFile, GlassFolder } from "@/components/ui/folder";
import { ArrowIcon } from "@/components/ui/icons";
import "@/features/auth/editorial.css";

/**
 * Not found (docs/DESIGN.md "Dark glass"): a lone glass folder lit from within by a red light,
 * holding one empty file, as if the page had been filed and taken out.
 */
export default function NotFoundPage() {
  return (
    <section className="lost">
      <div className="lost-folder-wrap" aria-hidden="true">
        <div className="lost-light" />
        <GlassFolder
          tone="ember"
          active
          className="lost-folder"
          tab={<span className="mono-label text-on-dark">Error // 404</span>}
          pocket={<span className="mono-label text-on-dark-soft">0 files</span>}
        >
          <GlassFile className="lost-file">
            <span className="mono-label text-muted">Untitled</span>
            <span className="lost-file-line" />
            <span className="lost-file-line lost-file-line-short" />
          </GlassFile>
        </GlassFolder>
      </div>
      <div className="flex flex-col items-center gap-5 text-center">
        <p className="mono-label text-primary">Quarterly // Not found</p>
        <h1 className="editorial-title">Page not found</h1>
        <p className="max-w-[30rem] text-body-md text-body">This folder is empty. The page may have moved, or the address may be mistyped.</p>
        <div className="flex flex-wrap justify-center gap-2">
          <Link to="/" className={buttonVariants()}>
            Go to the home page
            <ArrowIcon size={16} />
          </Link>
          <Link to="/courses" className={buttonVariants({ variant: "outline" })}>
            Search the catalog
          </Link>
        </div>
      </div>
    </section>
  );
}
