import { useEffect } from "react";

// Content stays visible without JS, observer support, or when motion is reduced.
export function useScrollReveal(rootRef, page) {
  useEffect(() => {
    const root = rootRef.current;
    if (!root || typeof IntersectionObserver === "undefined" || window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const seen = new WeakSet();
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("reveal-play");
        observer.unobserve(entry.target);
      });
    }, { threshold: 0.06 });
    const scan = () => root.querySelectorAll("[data-reveal], .panel").forEach(node => {
      if (seen.has(node)) return;
      seen.add(node); observer.observe(node);
    });
    scan();
    const changes = new MutationObserver(scan);
    changes.observe(root, { childList: true, subtree: true });
    return () => { observer.disconnect(); changes.disconnect(); };
  }, [rootRef, page]);
}
