import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

/**
 * Wraps a horizontally-scrollable table container and adds a sticky mirror
 * scrollbar that stays pinned to the bottom of the viewport so users don't
 * have to scroll all the way to the end of a tall table to scroll it horizontally.
 */
export function StickyScrollContainer({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const mirrorRef = useRef<HTMLDivElement>(null);
  const phantomRef = useRef<HTMLDivElement>(null);
  const syncing = useRef(false);

  useEffect(() => {
    const scroll = scrollRef.current;
    const mirror = mirrorRef.current;
    const phantom = phantomRef.current;
    if (!scroll || !mirror || !phantom) return;

    const syncWidth = () => {
      phantom.style.width = `${scroll.scrollWidth}px`;
    };
    syncWidth();
    const ro = new ResizeObserver(syncWidth);
    ro.observe(scroll);

    const onScrollContent = () => {
      if (syncing.current) return;
      syncing.current = true;
      mirror.scrollLeft = scroll.scrollLeft;
      syncing.current = false;
    };
    const onScrollMirror = () => {
      if (syncing.current) return;
      syncing.current = true;
      scroll.scrollLeft = mirror.scrollLeft;
      syncing.current = false;
    };

    scroll.addEventListener("scroll", onScrollContent, { passive: true });
    mirror.addEventListener("scroll", onScrollMirror, { passive: true });

    return () => {
      ro.disconnect();
      scroll.removeEventListener("scroll", onScrollContent);
      mirror.removeEventListener("scroll", onScrollMirror);
    };
  }, []);

  return (
    <div className="flex flex-col">
      <div ref={scrollRef} className={className}>
        {children}
      </div>
      {/* sticky mirror scrollbar — sticks to the bottom of the nearest scroll ancestor */}
      <div
        ref={mirrorRef}
        className="sticky bottom-0 overflow-x-scroll overflow-y-hidden"
        style={{ height: 12 }}
      >
        <div ref={phantomRef} style={{ height: 1 }} />
      </div>
    </div>
  );
}
