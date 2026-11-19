import { useEffect, useRef, useState, type ReactNode } from "react";
import katex from "katex";
import "katex/dist/katex.min.css";

type Block =
  | { kind: "paragraph"; text: string }
  | { kind: "heading"; level: number; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "code"; language: string; text: string }
  | { kind: "table"; header: string[]; rows: string[][] }
  | { kind: "rule" }
  | { kind: "image"; src: string; alt: string }
  | { kind: "figure"; src: string; alt: string; caption: string };

const BOOKFIG = /\{\{<\s*(?:bookfig|figure)\s+([\s\S]*?)\s*>\}\}/g;
const ATTRIBUTE = /([a-zA-Z_][\w-]*)\s*=\s*"([^"]*)"/g;
const IMAGE = /^!\[([^\]]*)\]\(([^)\s]+)\)\s*$/;

export function bookSlug(value: string): string {
  return slug(value);
}

function slug(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function splitFrontMatter(value: string): string {
  const match = /^\+\+\+\s*\n[\s\S]*?\n\+\+\+\s*\n?/.exec(value);
  return match ? value.slice(match[0].length) : value;
}

function shortcodes(value: string): Block[] {
  const blocks: Block[] = [];
  let cursor = 0;
  for (const match of value.matchAll(BOOKFIG)) {
    const before = value.slice(cursor, match.index ?? 0);
    if (before.trim()) blocks.push(...parseBlocks(before.split("\n")));
    const attrs: Record<string, string> = {};
    for (const attr of match[1].matchAll(ATTRIBUTE)) attrs[attr[1]] = attr[2];
    if (attrs.src) {
      blocks.push({
        kind: "figure",
        src: attrs.src,
        alt: attrs.alt ?? "",
        caption: attrs.caption ?? "",
      });
    }
    cursor = (match.index ?? 0) + match[0].length;
  }
  const rest = value.slice(cursor);
  if (rest.trim()) blocks.push(...parseBlocks(rest.split("\n")));
  return blocks;
}

function splitTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function parseBlocks(lines: string[]): Block[] {
  const blocks: Block[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }
    const image = IMAGE.exec(line.trim());
    if (image) {
      blocks.push({ kind: "image", alt: image[1], src: image[2] });
      index += 1;
      continue;
    }
    if (line.trim().startsWith("```")) {
      const language = line.trim().replace(/^```/, "").trim().toLowerCase();
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        body.push(lines[index]);
        index += 1;
      }
      index += 1;
      blocks.push({ kind: "code", language, text: body.join("\n") });
      continue;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      blocks.push({
        kind: "heading",
        level: heading[1].length,
        text: heading[2].trim(),
      });
      index += 1;
      continue;
    }
    if (/^---+$/.test(line.trim())) {
      blocks.push({ kind: "rule" });
      index += 1;
      continue;
    }
    if (line.trim().startsWith(">")) {
      const body: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        body.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
      }
      blocks.push({ kind: "quote", text: body.join(" ").trim() });
      continue;
    }
    const unordered = /^\s*[-*]\s+/.test(line);
    const ordered = /^\s*\d+\.\s+/.test(line);
    if (unordered || ordered) {
      const items: string[] = [];
      const pattern = ordered ? /^\s*\d+\.\s+/ : /^\s*[-*]\s+/;
      while (index < lines.length && pattern.test(lines[index])) {
        items.push(lines[index].replace(pattern, "").trim());
        index += 1;
      }
      blocks.push({ kind: "list", ordered, items });
      continue;
    }
    if (
      line.trim().startsWith("|") &&
      index + 1 < lines.length &&
      /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[index + 1])
    ) {
      const header = splitTableRow(line);
      index += 2;
      const rows: string[][] = [];
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        rows.push(splitTableRow(lines[index]));
        index += 1;
      }
      blocks.push({ kind: "table", header, rows });
      continue;
    }
    const paragraph: string[] = [];
    while (index < lines.length && lines[index].trim()) {
      const next = lines[index];
      if (
        /^(#{1,4})\s+/.test(next) ||
        next.trim().startsWith("```") ||
        next.trim().startsWith(">") ||
        /^\s*[-*]\s+/.test(next) ||
        /^\s*\d+\.\s+/.test(next) ||
        next.trim().startsWith("|") ||
        /^---+$/.test(next.trim()) ||
        IMAGE.test(next.trim())
      ) {
        break;
      }
      paragraph.push(next.trim());
      index += 1;
    }
    if (paragraph.length) blocks.push({ kind: "paragraph", text: paragraph.join(" ") });
  }
  return blocks;
}

function mathNode(value: string, key: string, display = false): ReactNode {
  try {
    return (
      <span
        key={key}
        className={display ? "book-math book-math-display" : "book-math"}
        dangerouslySetInnerHTML={{
          __html: katex.renderToString(value, {
            throwOnError: false,
            displayMode: display,
            output: "html",
          }),
        }}
      />
    );
  } catch {
    return <code key={key}>{value}</code>;
  }
}

function inline(value: string, keyPrefix: string): ReactNode[] {
  const pattern =
    /(\\\([\s\S]+?\\\)|\\\[[\s\S]+?\\\]|\*\*[^*]+\*\*|\*[^*\n]+\*|`[^`]+`|\[[^\]]+\]\((?:https?:\/\/|#)[^)\s]+\))/g;
  return value
    .split(pattern)
    .filter(Boolean)
    .map((part, index) => {
      const key = `${keyPrefix}-${index}`;
      if (part.startsWith("\\(") && part.endsWith("\\)")) {
        return mathNode(part.slice(2, -2), key);
      }
      if (part.startsWith("\\[") && part.endsWith("\\]")) {
        return mathNode(part.slice(2, -2), key, true);
      }
      if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
        return <strong key={key}>{inline(part.slice(2, -2), key)}</strong>;
      }
      if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
        return <code key={key}>{part.slice(1, -1)}</code>;
      }
      if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
        return <em key={key}>{inline(part.slice(1, -1), key)}</em>;
      }
      const link = /^\[([^\]]+)\]\(((?:https?:\/\/|#)[^)\s]+)\)$/.exec(part);
      if (link) {
        return (
          <a key={key} href={link[2]} target="_blank" rel="noreferrer">
            {link[1]}
          </a>
        );
      }
      return <span key={key}>{part}</span>;
    });
}

function assetUrl(projectId: string, src: string): string {
  const relative = src.replace(/^\.?\//, "").replace(/\\/g, "/");
  return `/api/living-book/projects/${encodeURIComponent(projectId)}/assets?path=${encodeURIComponent(relative)}`;
}

function MermaidBlock({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let live = true;
    const id = `book-mermaid-${Math.random().toString(36).slice(2)}`;
    void import("mermaid")
      .then(async ({ default: mermaid }) => {
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          theme: document.documentElement.dataset.theme === "light" ? "neutral" : "dark",
          fontFamily: "inherit",
        });
        const { svg } = await mermaid.render(id, code);
        if (live && ref.current) ref.current.innerHTML = svg;
      })
      .catch(() => {
        if (live) setError(true);
      });
    return () => {
      live = false;
    };
  }, [code]);
  if (error) {
    return (
      <pre className="markdown-code">
        <code>{code}</code>
      </pre>
    );
  }
  return <div className="book-mermaid" ref={ref} aria-label="Diagram" />;
}

export function BookMarkdown({
  content,
  projectId,
}: {
  content: string;
  projectId: string;
}) {
  const body = splitFrontMatter(content.replace(/\r\n/g, "\n"));
  const blocks = shortcodes(body);
  return (
    <div className="book-prose">
      {blocks.map((block, index) => {
        const key = `book-block-${index}`;
        if (block.kind === "heading") {
          const Tag = (`h${Math.min(block.level, 4)}` as "h1" | "h2" | "h3" | "h4");
          return (
            <Tag key={key} id={slug(block.text)}>
              {inline(block.text, key)}
            </Tag>
          );
        }
        if (block.kind === "paragraph") {
          return <p key={key}>{inline(block.text, key)}</p>;
        }
        if (block.kind === "quote") {
          return <blockquote key={key}>{inline(block.text, key)}</blockquote>;
        }
        if (block.kind === "code") {
          if (block.language === "mermaid") return <MermaidBlock key={key} code={block.text} />;
          return (
            <pre key={key} className="markdown-code">
              <code>{block.text}</code>
            </pre>
          );
        }
        if (block.kind === "rule") return <hr key={key} />;
        if (block.kind === "image") {
          return (
            <figure key={key} className="book-figure">
              <img src={assetUrl(projectId, block.src)} alt={block.alt} loading="lazy" />
              {block.alt ? <figcaption>{block.alt}</figcaption> : null}
            </figure>
          );
        }
        if (block.kind === "figure") {
          return (
            <figure key={key} className="book-figure">
              <img src={assetUrl(projectId, block.src)} alt={block.alt} loading="lazy" />
              {block.caption ? <figcaption>{inline(block.caption, key)}</figcaption> : null}
            </figure>
          );
        }
        if (block.kind === "table") {
          return (
            <div className="markdown-table-wrap" key={key}>
              <table className="markdown-table">
                <thead>
                  <tr>
                    {block.header.map((cell, cellIndex) => (
                      <th key={`${key}-h-${cellIndex}`}>{inline(cell, `${key}-h-${cellIndex}`)}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={`${key}-r-${rowIndex}`}>
                      {block.header.map((_cell, cellIndex) => (
                        <td key={`${key}-c-${rowIndex}-${cellIndex}`}>
                          {inline(row[cellIndex] || "", `${key}-c-${rowIndex}-${cellIndex}`)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
        const Tag = block.ordered ? "ol" : "ul";
        return (
          <Tag key={key}>
            {block.items.map((item, itemIndex) => (
              <li key={`${key}-${itemIndex}`}>{inline(item, `${key}-${itemIndex}`)}</li>
            ))}
          </Tag>
        );
      })}
    </div>
  );
}
