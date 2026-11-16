const P = {
  chat: "M4 5h16v10H8l-4 4z",
  compare: "M8 4v16M16 4v16M3 9h5M16 15h5",
  docs: "M6 3h8l4 4v14H6zM14 3v4h4M9 12h6M9 16h6",
  eval: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  settings: "M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1L7 17M17 7l2.1-2.1",
  status: "M3 12h4l3-8 4 16 3-8h4",
  send: "M4 12l16-8-6 16-2-7z",
  stop: "M7 7h10v10H7z",
  upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13",
  plus: "M12 5v14M5 12h14",
  chevron: "M9 6l6 6-6 6",
  ext: "M14 4h6v6M20 4l-9 9M18 14v6H4V6h6",
  check: "M5 12l5 5 9-10",
  x: "M6 6l12 12M18 6L6 18",
  refresh: "M20 12a8 8 0 11-2.3-5.7M20 4v5h-5",
};

export default function Icon({ name, size = 16, stroke = 1.8 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={stroke} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={P[name]} />
    </svg>
  );
}
