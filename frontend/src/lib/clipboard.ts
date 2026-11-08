function legacyCopy(text: string): void {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";
  document.body.appendChild(textarea);
  textarea.select();
  try {
    const copied =
      typeof document.execCommand === "function" && document.execCommand("copy");
    if (!copied) throw new Error("The clipboard is unavailable in this browser.");
  } finally {
    document.body.removeChild(textarea);
  }
}

async function clipboardWrite(text: string): Promise<boolean> {
  if (!navigator.clipboard?.writeText) return false;
  try {
    await Promise.race([
      navigator.clipboard.writeText(text),
      new Promise<never>((_resolve, reject) => {
        window.setTimeout(
          () => reject(new Error("Clipboard write did not complete.")),
          2000,
        );
      }),
    ]);
    return true;
  } catch {
    return false;
  }
}

export async function copyText(text: string): Promise<void> {
  if (await clipboardWrite(text)) return;
  // A browser may expose the clipboard API but withhold it without a trusted
  // gesture or permission. Fall back to the selection-based copy path so the
  // action cannot sit forever on "Copying…".
  legacyCopy(text);
}
