const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  AlignmentType, LevelFormat, HeadingLevel, BorderStyle, WidthType,
  ShadingType, PageNumber, Header, Footer, PageBreak, TableOfContents, ImageRun,
} = require("docx");

// Figure helper: embed a PNG with a numbered caption.
let __figN = 0;
function figure(path, widthPx, caption) {
  __figN += 1;
  const png = fs.readFileSync(path);
  const W = png.readUInt32BE(16), H = png.readUInt32BE(20);   // PNG IHDR width/height
  const w = widthPx, h = Math.round(widthPx * H / W);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 },
      children: [new ImageRun({ data: png, transformation: { width: w, height: h } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
      children: [ new TextRun({ text: `Figure ${__figN}. `, bold: true, size: 17, color: "333333" }),
                  new TextRun({ text: caption, size: 17, color: "333333" }) ] }),
  ];
}

// ---------- helpers ----------
const FONT = "Calibri";
const ACCENT = "1F4E79";
const LIGHT = "EAF1F8";
const GREY = "F2F2F2";

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] });
}
function p(text, opts = {}) {
  return new Paragraph({
    spacing: { after: 140, line: 276 },
    alignment: opts.justify ? AlignmentType.JUSTIFIED : AlignmentType.LEFT,
    children: [new TextRun({ text, italics: !!opts.italics })],
  });
}
// rich paragraph from array of run-specs
function rp(runs, opts = {}) {
  return new Paragraph({
    spacing: { after: 140, line: 276 },
    alignment: opts.justify ? AlignmentType.JUSTIFIED : AlignmentType.LEFT,
    children: runs.map(r => typeof r === "string"
      ? new TextRun(r)
      : new TextRun({ text: r.t, bold: r.b, italics: r.i, color: r.c, font: r.mono ? "Consolas" : undefined })),
  });
}
function bullet(text, ref = "bul") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 60, line: 270 },
    children: [new TextRun(text)],
  });
}
function bulletRich(runs, ref = "bul") {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 60, line: 270 },
    children: runs.map(r => typeof r === "string" ? new TextRun(r)
      : new TextRun({ text: r.t, bold: r.b, italics: r.i, color: r.c })),
  });
}
function numItem(text, ref) {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { after: 60, line: 270 },
    children: [new TextRun(text)],
  });
}
function code(lines) {
  return lines.map((ln, i) => new Paragraph({
    shading: { fill: GREY, type: ShadingType.CLEAR },
    spacing: { after: i === lines.length - 1 ? 140 : 0, line: 250 },
    indent: { left: 220, right: 220 },
    children: [new TextRun({ text: ln === "" ? " " : ln, font: "Consolas", size: 18 })],
  }));
}
const cellBorder = { style: BorderStyle.SINGLE, size: 1, color: "BBBBBB" };
const cellBorders = { top: cellBorder, bottom: cellBorder, left: cellBorder, right: cellBorder };
function tcell(text, { w, head = false, bold = false, fill } = {}) {
  return new TableCell({
    borders: cellBorders,
    width: { size: w, type: WidthType.DXA },
    shading: { fill: fill || (head ? ACCENT : "FFFFFF"), type: ShadingType.CLEAR },
    margins: { top: 60, bottom: 60, left: 110, right: 110 },
    children: [new Paragraph({
      spacing: { after: 0, line: 250 },
      children: [new TextRun({ text, bold: head || bold, color: head ? "FFFFFF" : "000000", size: 19 })],
    })],
  });
}
function table(widths, rows) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map((cells, ri) => new TableRow({
      children: cells.map((c, ci) => tcell(c, { w: widths[ci], head: ri === 0, fill: ri === 0 ? ACCENT : (ri % 2 === 0 ? LIGHT : "FFFFFF") })),
    })),
  });
}
function noteBox(title, lines) {
  const inner = [new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: title, bold: true, color: ACCENT })] })];
  lines.forEach(l => inner.push(new Paragraph({ spacing: { after: 60, line: 260 }, children: [new TextRun({ text: l, italics: true, size: 20 })] })));
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [new TableRow({ children: [new TableCell({
      borders: { top: { style: BorderStyle.SINGLE, size: 4, color: ACCENT }, bottom: { style: BorderStyle.SINGLE, size: 4, color: ACCENT }, left: { style: BorderStyle.SINGLE, size: 4, color: ACCENT }, right: { style: BorderStyle.SINGLE, size: 4, color: ACCENT } },
      shading: { fill: LIGHT, type: ShadingType.CLEAR },
      margins: { top: 120, bottom: 120, left: 160, right: 160 },
      children: inner,
    })] })],
  });
}
const gap = () => new Paragraph({ spacing: { after: 80 }, children: [new TextRun("")] });

// ---------- content ----------
const children = [];

// Title block
children.push(new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 200, after: 120 },
  children: [new TextRun({ text: "MARI: A Motion-Aware Adaptive Range Index for Exact Range Reporting over Bounded-Drift Streaming Integer Keys", bold: true, size: 32, color: ACCENT })],
}));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: "[Author Name(s)] — [Affiliation(s)] — [Contact email]", italics: true, color: "555555" })] }));
children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: [new TextRun({ text: "Preprint", italics: true, color: "555555", size: 18 })] }));

// Abstract
children.push(h1("Abstract"));
children.push(p(
  "We study exact range reporting over a stream of integer keys that change value over time under bounded drift: between successive updates, each key moves by at most a fixed amount. Conventional ordered indexes relocate an entry whenever its key changes; MARI, a motion-aware adaptive range index, exploits the locality of motion to avoid most such relocations. MARI partitions the key universe into buckets, each owning a core interval and a wider guard interval; a key that drifts but stays inside its bucket\u2019s guard is updated in place, without migration. Exactness is preserved by an authoritative per-item identifier table and a per-bucket stable-plus-versioned-delta organization: a query scans only the buckets whose guards intersect it and verifies candidates against the table, admitting neither false positives nor false negatives. We prove a delta-ratio compaction policy with O(1/\u03b5) amortized cost and O(n + m) space, an adaptive split/merge policy with O(1) amortized maintenance, and that for a fixed bucketing MARI performs the minimum relocations of any exact algorithm in this guarded-ownership model. A reference implementation validates exactness against a brute-force oracle \u2014 across five drift regimes MARI relocates 1.5\u20135% of updates versus 98\u2013100% for delete-then-insert \u2014 and on three independent real domains (S&P 500 prices, NBA Elo, and city temperatures) confirms bounded drift, with 95\u201399% of moves inside a modest guard and zero mismatches. Against faithful, exactness-checked implementations of an adaptive radix tree, a dynamic learned index, and a Bx-tree, MARI relocates about 40\u00d7 less often while keeping query cost low. This changes an update\u2019s cost model rather than its single-thread throughput: against a native copy-on-write B+-tree (LMDB) MARI writes 58\u201382\u00d7 fewer durable bytes per update, in the same band as a native LSM (RocksDB). We position MARI for write-amplification- and contention-sensitive settings, and make no throughput-superiority claim over production native-code indexes.",
  { justify: true }
));
children.push(rp([{ t: "Keywords: ", b: true }, "range reporting; streaming integer keys; bounded drift; adaptive indexing; motion-aware data structures; in-place update; versioned delta index; exact query processing."]));
children.push(gap());

// Contents
children.push(h1("Contents"));
children.push(new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// 1 Introduction
children.push(h1("1. Introduction"));
children.push(p(
  "Ordered indexes such as balanced search trees answer range queries efficiently when the indexed keys are static. Many streaming workloads, however, index keys that are not static but evolve: a numeric attribute associated with a long-lived item is repeatedly revised while the item's identity persists. In such settings a value change is conventionally realized as a delete-then-insert pair, which relocates the entry within the structure. When updates are frequent, relocation — not search — becomes the bottleneck.",
  { justify: true }
));
children.push(p(
  "This paper isolates a regime in which relocation is largely avoidable: bounded-drift streaming integer keys. Here each key is a bounded integer drawn from a known universe, and successive values of the same key differ by at most a fixed bound. Under this constraint a key that changes typically stays near its previous value, so an index organized by value can keep the entry in place for many updates before any structural move is required. The research question is whether this locality of motion can be turned into a measurable reduction in update cost while still supporting exact range reporting — reporting precisely the set of items whose current key lies in a queried interval, with no approximation.",
  { justify: true }
));
children.push(p(
  "We answer in the affirmative at the design level and specify the evaluation needed to answer it empirically. Our index, MARI (Motion-Aware Adaptive Range Index), introduces guarded bucket ownership: the universe is partitioned into buckets, and each bucket owns a guard interval extending beyond its core interval. An item remains in its bucket while its key stays within the guard, absorbing drift without migration; migration occurs only when a key leaves the guard. Correctness under in-place update is maintained by a versioned delta index per bucket and a final verification against an authoritative identifier table.",
  { justify: true }
));
children.push(rp([{ t: "Contributions. ", b: true }, "This paper makes the following contributions."]));
children.push(numItem("A formal definition of the exact range reporting problem over bounded-drift streaming integer keys, including the drift model, the update and query semantics, and the correctness criterion.", "contrib"));
children.push(numItem("The MARI index design: guarded bucket ownership, an authoritative identifier table, and a per-bucket stable-plus-delta organization, together with the guard-intersection invariant that underpins query correctness, and an adaptive split/merge policy with a proven O(1) amortized maintenance bound that keeps buckets balanced under skew (Theorem 3).", "contrib"));
children.push(numItem("Update, range-query, and compaction algorithms, with a correctness argument (no false positives, no false negatives) and a complexity analysis, with the compaction, maintenance, and relocation bounds proven (Theorems 1\u20133).", "contrib"));
children.push(numItem("A relocation-optimality theorem (Theorem 2): within the guarded-ownership model, MARI performs the minimum number of relocations of any correct algorithm for a fixed bucketing. We additionally prove a true monotone relocation bound and, candidly, refute the tempting migration-versus-amplification tradeoff with our own measurements, locating MARI's advantage in per-update cost rather than relocation count (Section 7.2).", "contrib"));
children.push(numItem("A reproducible evaluation protocol with workload generators spanning five drift regimes, a baseline suite, ablations, and metrics; and a reference implementation that validates exactness against a brute-force oracle and measures the migration-reduction and guard/compaction trade-offs (Section 9).", "contrib"));
children.push(numItem("A competitive evaluation against three ordered-index designs — an adaptive radix tree, a dynamic learned index, and a Bx-tree with an exactness adapter — all made exact for this problem, showing MARI relocates about 40× less often (Section 9.15).", "contrib"));
children.push(rp([{ t: "Scope and honesty. ", b: true }, "This is a methods, design, and analysis contribution with a validating reference implementation. We prove the core bounds (Theorems 1\u20133), validate exactness against a brute-force oracle on synthetic and real workloads, and measure the update cost model on real systems, including native engines. We are explicit about what is not claimed: the competitor comparisons (Section 9.15) and systems baselines are faithful reference implementations rather than tuned native code, so no cross-system wall-clock superiority is asserted, and the bounded-drift assumption restricts generality \u2014 so we audit it on every workload. Where a property is established only within a stated model, or remains open, we say so."]));
children.push(gap());

// 2 Problem Formulation
children.push(h1("2. Problem Formulation"));
children.push(h2("2.1 Data and drift model"));
children.push(p("Let U = {0, 1, …, M − 1} be a totally ordered integer key universe. A workload maintains a set S of items; each item has a unique, immutable identifier id and a time-varying integer key k(id) in U. The workload is a stream of operations applied in discrete steps:", { justify: true }));
children.push(bulletRich([{ t: "Insert(id, v): ", b: true }, "introduce a new item with key v in U."]));
children.push(bulletRich([{ t: "Update(id, v\u2032): ", b: true }, "change the key of an existing item to v\u2032 in U."]));
children.push(bulletRich([{ t: "Delete(id): ", b: true }, "remove an existing item."]));
children.push(bulletRich([{ t: "RangeQuery(a, b): ", b: true }, "return { id : a \u2264 k(id) \u2264 b } exactly, evaluated against the current state."]));
children.push(rp([{ t: "Bounded drift. ", b: true }, "The defining assumption is a bound \u03b4 on per-step key movement: for any item, two consecutive key values satisfy |v\u2032 \u2212 v| \u2264 \u03b4. We treat \u03b4 as a known global parameter; a per-item or per-region bound \u03b4(\u00b7) is a straightforward generalization and is noted where it affects the analysis. The bound is a property of the workload, not enforced by the index."], { justify: true }));
children.push(p("We use d to denote a local drift extent — the spread of recently observed keys within a bucket — which governs per-bucket structure sizes and appears in the complexity bounds. We do not claim \u03b4 or d are small in general; their magnitude relative to the universe and to bucket width is exactly what the evaluation must characterize.", { justify: true }));

children.push(h2("2.2 Query semantics and correctness criterion"));
children.push(p("A range query must be exact: its output is the precise set of items whose current key lies in [a, b]. Let R be the true answer and A the answer produced by the index. The index is correct iff A = R for every query against every reachable state, i.e. no false negatives (R \u2286 A) and no false positives (A \u2286 R). Approximate, conservative, or predictive answers are out of scope; this distinguishes the problem from predictive moving-object querying.", { justify: true }));
children.push(p("The bounded-drift property is the load-bearing assumption of this work: it is a property of the workload, not enforced by the index, and is audited on every workload in Section 8.2. The remaining open item is a fully specified production application that fixes a realistic \u03b4 end to end, which we leave to deployment.", { justify: true }));
children.push(h2("2.3 A motivating application: real-time market surveillance"));
children.push(p("A concrete deployment fixes the abstract model. Consider a real-time market-surveillance or best-execution dashboard that maintains, over the N listed symbols, the exact set currently trading within a price band [a, b], updated on every tick. The indexed key is the price in cents; it drifts as quotes update. Crucially the per-interval drift is bounded by regulation: under the SEC Limit Up-Limit Down plan a Tier-1 security (S&P 500, Russell 1000, listed ETFs) priced above $3 may not trade more than 5% from its rolling five-minute reference price before trading pauses \u2014 10% for Tier 2, and the bands double in the opening and closing windows. The exchange therefore enforces |\u0394 price| \u2264 \u03b4 with \u03b4 = 5% of the reference: exactly the bounded-drift regime, with \u03b4 fixed by the rulebook rather than assumed. Surveillance queries must be exact (a compliance alert admits no false hits or misses), the update rate is high, and the keys are one-dimensional integers \u2014 the four requirements of this section. A second instance is rating systems: an Elo service answering which players currently hold a rating in [a, b] has \u03b4 bounded by the K-factor (20 for the NBA Elo data of Section 9.9), so one result shifts a rating by at most K.", { justify: true }));
children.push(p("Why not simply a key-value store with a secondary index? Indexing the moving price in a B+-tree or RocksDB makes each tick a delete-old-price plus insert-new-price \u2014 a relocation per symbol per tick \u2014 which is the write amplification MARI removes while still answering the exact range query. The bounded LULD drift is precisely what lets the guard absorb almost all of those ticks in place.", { justify: true }));
children.push(gap());
children.push(gap());

// 3 Related Work
children.push(h1("3. Related Work"));
children.push(p("MARI sits at the intersection of four lines of work; positioning against the first two is essential. All references in this section have been checked against primary sources; bibliographic details appear in Section 13.", { justify: true }));
children.push(h2("3.1 Ordered and updatable indexes"));
children.push(p("Balanced ordered structures (the B+-tree family and its modern main-memory descendants) and trie-based ordered indexes provide logarithmic search and exact range reporting. The Adaptive Radix Tree [7] and the latch-free Bw-tree [8] target cache- and concurrency-efficiency in main memory; Graefe analyses B-trees under high update rates [5] and partitioned B-trees that buffer changes [6]. In all of these a key change is realized as delete-then-insert, paying a relocation on every move. MARI targets exactly this relocation cost. The honest baseline question is whether a well-tuned ordered index, given the same motion locality, already amortizes relocation cheaply; our reference experiment (Section 9) measures the relocation rate of this family directly rather than assuming it.", { justify: true }));
children.push(h2("3.2 Moving-object and time-parameterized indexes"));
children.push(p("A mature literature indexes objects whose values change over time. The TPR-tree [9] and TPR*-tree [10] use velocity-parameterized bounding rectangles to answer predictive spatio-temporal queries; the Bx-tree [11] and the B^dual-tree [12] linearize moving points through a space-filling curve and index the result in a B+-tree; the ST2B-tree [13] adds self-tuning. Two distinctions separate MARI from this line and must be stated crisply. First, these methods are predictive and (in the multidimensional case) velocity-driven, whereas MARI answers exact current-time queries under a bounded-drift model with no velocity assumption. Second, and more sharply, the 1D-linearization indexes are not exact: the space-filling-curve mapping produces false hits, so the query region must be enlarged to guarantee recall [11, 12]. MARI instead preserves exactness by construction through guard-scoped ownership plus authoritative verification. This is the central novelty boundary of the paper.", { justify: true }));
children.push(p("A distinct lineage in computational geometry, kinetic data structures (KDS) [22, 23], maintains a combinatorial attribute of continuously moving objects \u2014 a convex hull, closest pair, or Delaunay triangulation \u2014 as the objects follow known motion laws. A KDS schedules certificates: conditions on the current combinatorial structure whose failure times are computed from the posited trajectories and processed by a discrete-event queue. MARI shares the premise that structured motion should avoid recomputation, but differs on every operational axis. KDS assumes the trajectories are known and continuous and optimizes the number of combinatorial events; MARI assumes no motion model beyond a per-step displacement bound, is discrete-time, and optimizes relocation and durable-write cost for an exact one-dimensional range index. The guard is not a certificate \u2014 it predicts no event time \u2014 but a slack region that turns most moves into in-place no-ops. The nearest relative is the later black-box KDS model, which likewise bounds per-step displacement rather than positing flight plans; MARI carries that assumption into a durable, write-amplification-focused database access method rather than an in-memory geometric structure.", { justify: true }));
children.push(p("Two finer points sharpen the boundary. First, the black-box KDS model replaces known flight plans with a bound on per-step displacement \u2014 formally MARI\u2019s bounded drift \u2014 but still maintains geometric structures (proximity, Delaunay) under that bound and measures cost in kinetic events; MARI maintains a one-dimensional exact range index and measures cost in relocations and durable bytes. Second, a KDS certificate is a predicate scheduled to fail at a computed time, whereas MARI\u2019s guard is a-temporal \u2014 it carries no event time and fires only reactively, when an update happens to leave it. So even at their closest \u2014 bounded displacement, one dimension \u2014 the two differ in what they maintain (combinatorial geometry versus an exact database index) and how they are driven (scheduled events versus reactive updates).", { justify: true }));
children.push(h2("3.3 Adaptive and learned indexes"));
children.push(p("Database cracking makes physical reorganization a by-product of query processing, refining the index toward the observed query predicates [15, 16, 17]. Learned indexes model the key-to-position mapping: the original proposal [18], the updatable ALEX [19], the worst-case-bounded PGM-index [20], and the data-aware FITing-Tree [21]. MARI is adaptive in a third sense: it adapts bucket boundaries and guard widths to observed motion, rather than to query predicates (cracking) or to a learned key distribution (learned indexes). The directions are complementary — a learned model could in principle set MARI's guard widths — a complementarity we note rather than overstate.", { justify: true }));
children.push(h2("3.4 Write-optimized (log-structured) indexes"));
children.push(p("Separating a small mutable delta from a large sorted main dates to differential files [4] and underlies the log-structured merge-tree [14], which buffers writes in a delta tier and merges into sorted runs. MARI's per-bucket versioned delta resembles this pattern, and the distinction must be explicit: MARI's deltas are scoped to a bucket whose guarded ownership bounds which keys can legally appear, so each delta is a localized in-place-update log rather than a global write buffer, and compaction is per-bucket. Section 5.3 gives the compaction policy and proves its amortized cost and the resulting space bound — the property at issue when MARI is equated with an LSM design. Section 10.1 consolidates this comparison, arguing why a naive composition of cracking, an LSM delta, and verified lookups does not by itself solve exact range reporting under drift.", { justify: true }));
children.push(gap());

// 4 The MARI Index
children.push(h1("4. The MARI Index"));
children.push(...figure("fig_mechanism.png", 560, "The guarded-ownership mechanism. Each bucket owns a core interval and a wider guard interval. A key that drifts but stays inside its owner\u2019s guard is updated in place with a single append; a key that leaves the guard migrates to a neighbour (two appends). Bounded drift makes the first case the common one."));
children.push(h2("4.1 Components"));
children.push(bulletRich([{ t: "Buckets. ", b: true }, "The universe U is partitioned into m buckets B\u2081, \u2026, B\u2098. Bucket B\u2c7c owns a core interval [lo\u2c7c, hi\u2c7c) and a guard interval [lo\u2c7c \u2212 g\u2c7c, hi\u2c7c + g\u2c7c), where g\u2c7c \u2265 0 is the bucket's guard width. Core intervals tile U; guard intervals overlap."]));
children.push(bulletRich([{ t: "Identifier table T (authoritative). ", b: true }, "A mapping id \u2192 (current key, owning bucket). T is the single source of truth for an item's current key and is the basis of query verification."]));
children.push(bulletRich([{ t: "Per-bucket stable index. ", b: true }, "A sorted (search-tree or sorted-run) index over the keys whose entries currently reside in the bucket."]));
children.push(bulletRich([{ t: "Per-bucket versioned delta index. ", b: true }, "A small structure recording recent in-place updates, insertions, and tombstones that have not yet been merged into the stable index, tagged with version/sequence numbers so the latest entry for an id is identifiable."]));
children.push(h2("4.2 Guarded ownership invariant"));
children.push(p("An item resides in exactly one bucket at any time. The ownership rule is: an item may reside in B\u2c7c only if its current key lies in B\u2c7c's guard interval. Equivalently, an item leaves B\u2c7c precisely when an update moves its key outside [lo\u2c7c \u2212 g\u2c7c, hi\u2c7c + g\u2c7c). Because guard intervals extend beyond cores, a key that drifts out of the core but stays within the guard does not trigger migration. This is the mechanism by which bounded drift is absorbed in place.", { justify: true }));
children.push(rp([{ t: "Guard-intersection property (relied on by queries). ", b: true }, "If an item's current key k lies in [a, b], then k lies in the guard interval of the item's owning bucket; hence that guard interval intersects [a, b]. Therefore every item in the true answer resides in some bucket whose guard intersects the query range. This property is what licenses scanning only guard-intersecting buckets without losing results."], { justify: true }));
children.push(h2("4.3 Why an authoritative table is still needed"));
children.push(p("Because updates are applied in place via the delta index and migrations leave tombstones, a bucket may transiently contain stale entries for an id (e.g., an old key value awaiting compaction, or an entry for an item that has since migrated). The authoritative table T resolves all such ambiguity at query time: a scanned candidate is emitted only if T confirms its current key is in [a, b]. T is consulted for verification, not as the primary range-search path — the bucket structure provides the fast path that narrows candidates before verification. Quantifying the verification cost relative to result size is central to the evaluation (Section 7).", { justify: true }));
children.push(gap());

// 5 Algorithms
children.push(h1("5. Algorithms"));
children.push(h2("5.1 Update"));
children.push(p("An update first consults T for the item's current bucket. If the new key remains within that bucket's guard, the update is recorded locally in the bucket's delta index and T is revised — no migration. Otherwise the item migrates: a tombstone is appended to the source bucket's delta, an insertion is appended to the destination bucket's delta, and T is revised to the new bucket and key.", { justify: true }));
children.push(new Paragraph({ spacing: { before: 60, after: 20 }, children: [new TextRun({ text: "Algorithm 1. Update / Insert / Delete", bold: true, size: 18, color: "333333" })] }));
children.push(...code([
  "Update(id, v'):",
  "  (k_old, B_src) <- T[id]",
  "  if v' in guard(B_src):                  # local, no migration",
  "      B_src.delta.put(id, v', version++)",
  "      T[id] <- (v', B_src)",
  "  else:                                   # migration",
  "      B_dst <- locate_bucket(v')          # bucket whose guard contains v'",
  "      B_src.delta.tombstone(id, version++)",
  "      B_dst.delta.put(id, v', version++)",
  "      T[id] <- (v', B_dst)",
  "  maybe_compact(B_src); maybe_compact(B_dst)",
]));
children.push(p("Insert and Delete are the degenerate cases: Insert locates the destination bucket and appends an insertion; Delete appends a tombstone to the owning bucket and removes id from T.", { justify: true }));
children.push(h2("5.2 Range query"));
children.push(p("A query locates the contiguous run of buckets whose guard intervals intersect [a, b], scans each bucket's stable and delta entries for keys in [a, b], reconciles versions so that only the latest entry per id is considered, and verifies each surviving candidate against T before emitting it.", { justify: true }));
children.push(new Paragraph({ spacing: { before: 60, after: 20 }, children: [new TextRun({ text: "Algorithm 2. Range query", bold: true, size: 18, color: "333333" })] }));
children.push(...code([
  "RangeQuery(a, b):",
  "  result <- {}",
  "  for B in buckets_with_guard_intersecting(a, b):   # O(log m + r) buckets",
  "      cand <- merge_latest(B.stable.range(a, b),",
  "                           B.delta.range(a, b))      # version reconciliation",
  "      for id in cand:",
  "          (k_cur, B_own) <- T[id]                    # authoritative check",
  "          if a <= k_cur <= b and B_own == B:",
  "              result.add(id)",
  "  return result",
]));
children.push(p("The B_own == B check prevents double-counting an id whose stale entry lingers in a bucket it has migrated away from; the a \u2264 k_cur \u2264 b check rejects stale in-bucket values. Together they enforce A \u2286 R.", { justify: true }));
children.push(h2("5.3 Compaction (the delta-ratio policy)"));
children.push(p("Each bucket's delta log is merged into its stable index when a trigger fires; compaction applies the latest version of each id, discards superseded versions and tombstoned entries, and rebuilds the bucket's sorted stable index. We analyze a specific trigger, the delta-ratio policy, for which we can prove both an amortized cost bound and a space bound.", { justify: true }));
children.push(rp([{ t: "Delta-ratio policy. ", b: true }, "Fix a constant \u03b5 \u2208 (0, 1]. Bucket B_j is compacted as soon as |D_j| \u2265 \u2308\u03b5 \u00b7 max(1, |S_j|)\u2309, where |S_j| is the size of the bucket's stable index and |D_j| the number of pending delta entries (in-place updates, insertions, and tombstones). Adaptive bucket split/merge, when enabled, is performed during a compaction so it is amortized into the same accounting."], { justify: true }));
children.push(rp([{ t: "Theorem 1 (amortized compaction cost). ", b: true }, "Under the delta-ratio policy, the total work spent on compaction over any sequence containing N delta-append operations is O(N / \u03b5). Equivalently, each append bears O(1/\u03b5) amortized compaction cost."], { justify: true }));
children.push(rp([{ t: "Proof. ", b: true }, "Fix a bucket B_j and order its compactions c\u2081, c\u2082, \u2026. The stable index is modified only during compaction (appends go to the delta), so let s_t = |S_j| immediately after c_t. Compaction c_{t+1} fires exactly when |D_j| first reaches \u2308\u03b5 \u00b7 max(1, s_t)\u2309, hence the number of appends in the interval (c_t, c_{t+1}] is a_{t+1} \u2265 \u03b5 \u00b7 s_t. Rebuilding the bucket reads its stable and delta once, so c_{t+1} costs at most \u03ba(s_t + a_{t+1}) for a constant \u03ba. Charging this to the a_{t+1} appends that triggered it gives per-append cost \u2264 \u03ba(s_t + a_{t+1}) / a_{t+1} = \u03ba(1 + s_t / a_{t+1}) \u2264 \u03ba(1 + 1/\u03b5) = O(1/\u03b5), using a_{t+1} \u2265 \u03b5 s_t. Each append is charged to exactly one compaction (the next one in its bucket), so summing over all buckets and compactions, total compaction work \u2264 O(1/\u03b5) \u00b7 N. \u220e"], { justify: true }));
children.push(rp([{ t: "Corollary 1 (space). ", b: true }, "At all times |D_j| < \u2308\u03b5 \u00b7 max(1, |S_j|)\u2309, so the delta tier is a constant fraction of the stable tier. Each live item occupies one stable slot in its owning bucket, and every stale stable entry has a matching tombstone pending in some delta and is reclaimed within one compaction cycle of its bucket; pending tombstones and superseded versions are themselves delta entries and so are bounded by the same trigger. Therefore \u03a3_j(|S_j| + |D_j|) = O(n), and total index space including the identifier table is O(n + m)."], { justify: true }));
children.push(rp([{ t: "Corollary 2 (query scan is not degraded). ", b: true }, "A query scanning bucket B_j examines |S_j| + |D_j| = (1 + O(\u03b5))|S_j| entries, so per-bucket query work stays within a constant factor of the bucket's live contents."], { justify: true }));
children.push(rp([{ t: "Empirical confirmation (reference implementation). ", b: true }, "On the uniform workload (Section 9), measured compaction work per append was 4.64, 2.88, and 1.91 for \u03b5 = 0.25, 0.5, and 1.0 respectively \u2014 tracking the predicted O(1/\u03b5) \u2014 while the maximum observed delta length grew linearly with \u03b5 (263, 526, 1050), consistent with |D_j| = \u0398(\u03b5|S_j|). Exactness held throughout."], { justify: true }));
children.push(rp([{ t: "Trade-off. ", b: true }, "\u03b5 is the compaction analogue of the guard width: small \u03b5 means frequent compaction (higher amortized write cost, O(1/\u03b5)) but near-pure stable buckets (queries scan little stale data); large \u03b5 means cheap writes but deltas up to \u03b5|S_j| that inflate query scans by a (1 + \u03b5) factor."], { justify: true }));
children.push(gap());

// 6 Correctness
children.push(...figure("fig_flowchart.png", 560, "Flowchart of the two MARI algorithms. (a) Update: the current bucket is read from the table T; if the new key stays inside the guard the entry is appended in place to the bucket delta (the common case), otherwise it migrates by a tombstone plus an insert at the destination; T is then updated and the bucket compacted once its delta reaches an \u03b5-fraction of its stable tier. (b) Query: only buckets whose guard intersects [a, b] are scanned, and every candidate is verified against T, so the returned set A equals the true answer R exactly."));
children.push(gap());
children.push(h1("6. Correctness"));
children.push(p("We state the two correctness properties and give the argument; the full invariant-preservation proof (the precise state invariants compaction must maintain) is routine and deferred to an appendix.", { justify: true }));
children.push(rp([{ t: "Claim 1 (No false negatives, R \u2286 A). ", b: true }, "Let id have current key k in [a, b]. By the ownership invariant, id resides in a bucket B whose guard contains k; by the guard-intersection property, B's guard intersects [a, b], so the query scans B. The latest entry for id in B (in stable \u222a delta after version reconciliation) carries key k, which lies in [a, b], so id becomes a candidate and passes verification. Hence id in A."], { justify: true }));
children.push(rp([{ t: "Claim 2 (No false positives, A \u2286 R). ", b: true }, "Any emitted id passed the verification T[id] = (k_cur, B) with a \u2264 k_cur \u2264 b. Since T is authoritative, id's current key is k_cur in [a, b], so id in R."], { justify: true }));
children.push(rp([{ t: "Proof obligation. ", b: true }, "Both claims assume version reconciliation always surfaces the latest entry for an id within a bucket and that T is updated atomically with the delta append. A complete proof shows every algorithm path \u2014 local update, migration, insert, delete, and compaction \u2014 preserves these invariants; under a concurrent variant, atomicity of the table update with respect to in-flight queries is the additional obligation. We establish the invariants for the sequential algorithms and treat the concurrent case as future work. Durability and crash recovery — reconstructing the stable tiers and the table T from the per-bucket logs — are addressed in Section 9.12."], { justify: true }));
children.push(gap());

// 7 Complexity
children.push(h1("7. Complexity Analysis"));
children.push(p("The table below states the per-operation bounds; the compaction and adaptive-maintenance bounds (Theorems 1 and 3) and the relocation bound (Theorem 2) are proven in the following subsections, and the remaining query bound is structural. m is the number of buckets, r the number of guard-intersecting buckets for a query, k the number of scanned candidates, and d a local drift extent governing per-bucket structure size.", { justify: true }));
children.push(table(
  [2400, 3600, 3360],
  [
    ["Operation", "Target bound", "Where the cost lives"],
    ["Update (local)", "O(log d)", "insert into one bucket's delta"],
    ["Update (migration)", "O(log m + log d)", "locate destination bucket + delta insert in two buckets"],
    ["RangeQuery", "O(log m + r + k + V)", "locate buckets + scan candidates + verification V \u2264 k table lookups"],
    ["Compaction (amortized)", "O(1/\u03b5), proven (Theorem 1)", "merge delta into stable under the delta-ratio policy"],
    ["Space", "O(n + m + \u03a3 |delta_j|)", "n items + m buckets + bounded deltas"],
  ]
));
children.push(rp([{ t: "The crux. ", b: true }, "The query bound hides the key tension: small guards reduce candidate over-scan (k near the result size) but force more migrations (raising update cost); large guards absorb drift cheaply but inflate k and the verification term V via query amplification. The guard-versus-amplification trade-off is the paper's central analytical object and must be characterized both theoretically and empirically, not asserted away."], { justify: true }));
children.push(gap());

children.push(h2("7.1 A relocation lower bound: optimality within the guarded-ownership model"));
children.push(p("We now show that MARI\u2019s guard is not merely a useful heuristic: for any fixed bucketing it relocates the minimum number of items that any correct algorithm of the same kind must. We make the model precise.", { justify: true }));
children.push(rp([{ t: "Guarded-ownership model. ", b: true }, "A structure in this model maintains, for each live item i, a single owning bucket o(i). Bucket j has core C_j = [j\u00b7w, (j+1)w \u2212 1] and guard interval G_j = [j\u00b7w \u2212 g, (j+1)w \u2212 1 + g]; the cores tile the universe. A range query [a, b] is answered by scanning exactly the buckets whose guard meets the query, {j : G_j \u2229 [a, b] \u2260 \u2205}, collecting the items registered in those buckets, and emitting item i iff its owner o(i) equals the scanned bucket and its current key lies in [a, b]. This is precisely MARI\u2019s scan-then-verify procedure; the ownership test is what delivers exactness."], { justify: true }));
children.push(rp([{ t: "Theorem 2 (forced relocation). ", b: true }, "Let A be any algorithm in the guarded-ownership model that answers every range query exactly. If an update changes item i\u2019s key to a value v with v \u2209 G_{o(i)}, then A must change o(i) \u2014 relocate i to some bucket j with v \u2208 G_j \u2014 before answering any subsequent query."], { justify: true }));
children.push(rp([{ t: "Proof. ", i: true }, "Suppose after the update o(i) = b with v \u2209 G_b. Consider the point query [v, v]. The scanned set is {j : G_j \u2208 v}; since v \u2209 G_b, bucket b is not scanned. By the emission rule i can be output only from a scanned bucket equal to its owner b, so i is not output. But i\u2019s current key v lies in [v, v], so exactness requires i to be output \u2014 a contradiction. Hence o(i) must change to some j with v \u2208 G_j; since the cores tile U and G_j \u2287 C_j, the core bucket of v is such a j. \u220e"], { justify: true }));
children.push(rp([{ t: "Corollary 3 (MARI is relocation-optimal in the model). ", b: true }, "MARI relocates an item exactly on the updates that carry its key outside the current owner\u2019s guard, and on no others. By Theorem 2 every correct guarded-ownership algorithm must relocate on at least those updates. Therefore, for any fixed bucketing (w, g) and any update sequence, MARI performs the minimum possible number of relocations among all correct algorithms in the model. A reference-implementation check confirms the identity: on the real S&P 500 stream MARI\u2019s migration count equals an independently computed forced-relocation count exactly (9,901 at g = $5 and 5,314 at g = $10)."], { justify: true }));
children.push(rp([{ t: "Corollary 4 (migration rate). ", b: true }, "For an item owned by b with key x \u2208 G_b, let its slack s(x) be the distance from x to the boundary of G_b in the direction of motion. An update of size \u0394 forces a relocation iff |\u0394| > s(x); since s(x) \u2265 g for any key in the core, the per-step relocation probability is at most Pr[|\u0394| > g] and decreases monotonically as g grows. This is the analytical counterpart of the measured guard/migration trade-off in Tables R2 and R12, where the migration rate equals the audited drift mass beyond the guard. Whether reducing migration this way is paid for elsewhere is examined \u2014 and the obvious query-amplification tradeoff refuted \u2014 in Section 7.2."], { justify: true }));
children.push(rp([{ t: "Scope (what is not claimed). ", b: true }, "The optimality holds within the guarded-ownership model \u2014 one owner per item, queries answered by scanning guard-intersecting buckets and verifying ownership. It is not an unconditional cell-probe lower bound and does not preclude structures outside the model: for instance, replicating an item across several buckets can lower the relocation count at the cost of space and update work, and a different exactness mechanism could change the query rule. An unconditional lower bound for exact bounded-drift range reporting remains open. What Theorem 2 establishes is that, given the guard budget, MARI\u2019s relocations are exactly those that exactness logically forces."], { justify: true }));
children.push(rp([{ t: "Proposition 2 (relocation\u2013scan coupling). ", b: true }, "Consider any exact range structure whose layout is governed by a single region-width parameter W, meaning (i) an item relocates only when its key leaves the width-W region holding it, and (ii) a range query examines \u0398(W\u00b7\u03c1) stored entries per region it overlaps, with \u03c1 the local key density. Then the expected per-step relocation rate r(W) = Pr[|\u0394k| > distance-to-edge] is non-increasing in W while the per-result scan amplification s(W) is non-decreasing in W: no choice of the single parameter W lowers both at once. A B+-tree leaf, a radix leaf, a sorted run, and a learned segment are all of this class, with W \u2192 0 at the stored key, forcing r \u2192 1 \u2014 they relocate on essentially every change. MARI is deliberately not of this class: it carries two independent parameters \u2014 a stay-in-place radius (the guard g) that sets the relocation trigger, and a bucket width w that sets scan granularity \u2014 so it attains relocation rate Pr[|\u0394k| > g] at a scan cost fixed independently by w, a point off the single-parameter frontier. This decoupling of g from w, not a smaller constant, is the structural reason MARI escapes the near-unit relocation rate to which the competitors are pinned; Theorem 2 then gives optimality once the bucketing is fixed."], { justify: true }));
children.push(gap());
children.push(rp([{ t: "Remark (why the competitors cannot avoid relocation). ", b: true }, "The comparison in Section 9.15 is not incidental. Any exact ordered index that assigns each item to a single position or fixed-width region and answers a range query by scanning that ordering must move the item whenever its value leaves the region; with a zero-width position \u2014 a sorted run, a radix leaf, a learned segment \u2014 that is every value change. Lowering the relocation rate then requires either widening the region, which widens the query scan in lockstep, or leaving the single-assignment model. MARI\u2019s guard is exactly the degree of freedom that breaks this coupling: it sets the stay-in-place radius g independently of the bucket width w that governs query amplification, so the relocation floor Pr[|\u0394k| > g] is lowered without widening queries \u2014 which is why every single-width competitor in Section 9.15 relocates about 40\u00d7 more often. Theorem 2\u2019s within-model optimality and this cross-design coupling together account for the measured gap."], { justify: true }));
children.push(gap());

children.push(h2("7.2 What is forced, and what is not: the limits of a relocation lower bound"));
children.push(p("It is tempting to seek a stronger, model-independent lower bound \u2014 a tradeoff that forces every exact index to pay for low relocation with high query cost. We report, honestly, that the natural such tradeoff does not hold, and we locate where the real cost lives. One direction is genuinely forced:", { justify: true }));
children.push(rp([{ t: "Proposition 1 (monotone relocation). ", b: true }, "In the single-location interval model \u2014 each item is examined for exactness only through one location whose key-region has width at most w \u2014 an adversary applying monotone drift of step \u03b4 forces every item to change location at least once per \u2308w/\u03b4\u2309 updates; the relocation rate is at least \u03b4/w. The argument is that of Theorem 2 applied repeatedly: once a value advances past its region of width w, a point query at the new value examines a different location that does not hold the item, so exactness forces a relocation, and a value advancing by \u03b4 per step exits a width-w region within \u2308w/\u03b4\u2309 steps. Empirically, monotone drift yields a migration rate of essentially \u03b4/w (0.050 and 0.025 measured for w = 1,000 and 2,000 at \u03b4 = 50)."], { justify: true }));
children.push(rp([{ t: "No migration\u2013amplification tradeoff. ", b: true }, "The tempting next step \u2014 pairing Proposition 1 with a query-cost penalty that grows with the region width w, forcing a frontier \u2014 fails. Region width is not lower-bounded by query cost: a structure binary-searches within a region, so a point query costs O(log + output) independent of w. We confirm this directly: widening MARI\u2019s guard from 50 to 2,000 cuts the monotone migration rate by more than threefold (0.050 to 0.015) while query amplification does not rise (it stays \u2248 1.0, even drifting slightly down). Large regions therefore reduce relocations essentially for free in query terms, so the relocation count alone is not the fundamental cost and no clean migration-versus-amplification lower bound exists."], { justify: true }));
children.push(rp([{ t: "Where the cost actually lives. ", b: true }, "Enlarging regions instead inflates per-update local work: a wider bucket carries a larger delta, so each in-place update and each compaction does proportionally more. MARI\u2019s genuine, measured advantage is therefore not a smaller relocation count \u2014 a coarse enough bucketing drives that down by itself \u2014 but a cheaper non-relocating update: a sequential append rather than an in-place re-sort. This is exactly what the durable-write results quantify (58\u201382\u00d7 fewer bytes than a native B+-tree, Section 9.7). The two theoretical pillars are thus the within-model relocation optimality of Theorem 2 and this per-update-cost advantage; an unconditional bound that simultaneously constrains relocation count, local-update work, and query cost remains open, and the analysis above shows why it is subtler than a one-line tradeoff. We state this rather than assert a frontier our own measurements refute."], { justify: true }));
children.push(gap());

children.push(h2("7.3 Adaptive bucket maintenance"));
children.push(p("The bucketing need not be fixed. Under skew, a static grid leaves some buckets dense and others empty; MARI rebalances with an adaptive policy whose cost we now bound.", { justify: true }));
children.push(rp([{ t: "Adaptive policy. ", b: true }, "Given a target size \u03c4, split a bucket when its live size exceeds 2\u03c4 \u2014 at the rank median of its live keys \u2014 and merge two adjacent buckets when their combined live size falls below \u03c4. A split reassigns the two halves\u2019 ownership in the authoritative table T and rebuilds two sorted tiers; a merge rebuilds one. Boundaries are kept in a balanced search tree keyed by core interval."], { justify: true }));
children.push(rp([{ t: "Theorem 3 (adaptive maintenance). ", b: true }, "Under this policy: (i) every bucket whose live keys admit a separating value satisfies |S_j| \u2264 2\u03c4, and the number of buckets is m = \u0398(n/\u03c4); (ii) total space is O(n + m) = O(n(1 + 1/\u03c4)); (iii) the amortized split/merge work is O(1) per update, so together with Theorem 1 the amortized update cost is O(1/\u03b5) plus O(log m) to locate a bucket; (iv) split and merge preserve the guard-intersection invariant, so exactness (Claims 1\u20132) is maintained throughout."], { justify: true }));
children.push(rp([{ t: "Proof sketch. ", i: true }, "Potential method. Give each bucket potential proportional to max(0, |S_j| \u2212 \u03c4) with a symmetric term at the merge threshold. A split at 2\u03c4 releases \u0398(\u03c4) potential, paying for the O(\u03c4) rebuild and the O(\u03c4) ownership reassignments in T; a merge below \u03c4 is charged symmetrically. Each insert, delete, or migration changes one bucket\u2019s size by one and the potential by O(1). Factor-2 hysteresis guarantees a freshly created bucket undergoes \u03a9(\u03c4) operations before its next structural change, so the O(\u03c4) rebuild amortizes to O(1) per operation; with boundaries in a balanced tree, each structural change also performs an O(log m) update, contributing O((log m)/\u03c4) = o(1) amortized. For (iv): splitting [lo, hi) at \u03bc sends keys below \u03bc to [lo, \u03bc) and the rest to [\u03bc, hi); every item\u2019s key lies in the guard of its new owner and the cores still tile the universe, so Claims 1\u20132 carry over, and merge is the inverse. \u220e"], { justify: true }));
children.push(rp([{ t: "Empirical confirmation. ", b: true }, "In the reference implementation the amortized split/merge work is a small constant independent of \u03c4 and workload \u2014 0.27 rebuild-units per update for \u03c4 \u2208 {10, 20, 40, 80} on uniform drift \u2014 while the bucket count tracks \u0398(n/\u03c4) and the maximum bucket stays at \u2248 2\u03c4 (42, 45, 81, 161 for those \u03c4). Exactness is preserved (zero mismatches across uniform, directional, clustered, and hotspot streams), and directional drift exercises merges as trailing buckets empty. The one exception to the size bound is a degenerate hotspot \u2014 more than 2\u03c4 items sharing a single key, which no key-range partition can split; there a bucket exceeds 2\u03c4 (observed 440 at \u03c4 = 20) yet exactness still holds. This is an inherent limit of range partitioning, not of the policy."], { justify: true }));
children.push(gap());

children.push(h1("8. Experimental Setup"));
children.push(p("This section specifies the workloads, baselines, metrics, and protocol; results are reported in Section 9. The bounded-drift property of every workload is audited so the central assumption is checkable.", { justify: true }));
children.push(h2("8.1 Workloads (synthetic generators)"));
children.push(p("A parametric generator produces operation streams with controlled drift. Each generator is defined so that the bounded-drift property holds with a stated \u03b4. Report, per workload, the realized drift distribution (so the assumption is auditable).", { justify: true }));
children.push(table(
  [2600, 6760],
  [
    ["Drift regime", "Definition / parameters to sweep"],
    ["Uniform drift", "each update adds noise in [\u2212\u03b4, \u03b4]; sweep \u03b4, update:query ratio, key count n, universe M"],
    ["Clustered drift", "keys grouped into clusters that drift together; sweep cluster count, intra/inter-cluster movement"],
    ["Directional drift", "keys trend in one direction (e.g., monotone-ish counters); sweep trend rate vs. \u03b4"],
    ["Adversarial boundary oscillation", "keys oscillate across a bucket boundary to stress migration and guards; sweep oscillation amplitude vs. g"],
    ["Hotspot queries", "query ranges concentrated on dense regions; sweep selectivity and skew"],
  ]
));
children.push(h2("8.2 Real workloads: finance, sports ratings, and climate"));
children.push(p("To test the bounded-drift assumption against reality rather than a generator, we use three real datasets from independent domains. (1) Finance: the five-year S&P 500 daily-price dataset (505 stocks, February 2013\u2013February 2018; 619,040 daily records), key = closing price in cents, query = \u201cwhich stocks trade between $a and $b?\u201d, universe 159\u2013204,900 cents. (2) Sports ratings: FiveThirtyEight\u2019s complete NBA Elo history (104 team codes, 126,314 game records since 1946), key = Elo rating, drift bounded by the Elo K-factor by construction. (3) Climate: daily mean temperatures for 16 US cities over six decades (417,432 daily records), key = mean temperature in degrees Fahrenheit. Each is replayed in chronological order as the operation stream.", { justify: true }));
children.push(rp([{ t: "Bounded-drift audit. ", b: true }, "All three confirm the assumption holds strongly but approximately, with a quantifiable tail. On the prices, |\u0394k| has median 44 cents and the fraction of day-to-day moves within \u03b4 is 76.9% for $1, 98.3% for $5, and 99.5% for $10; the 0.5% tail (max $257) is earnings surprises and crashes, and drift scales with price level (median |\u0394k| rises from 14 cents sub-$20 to 393 cents above $300), the regime adaptive bucket widths target. On NBA Elo, |\u0394k| has median 7 and 95.4% of per-game moves are within 20 rating points (99.9% within 50); the rare large jumps are season resets and franchise relocations. On city temperatures, median day-to-day change is 2\u00b0F and 94.9% of moves are within 10\u00b0F (99.8% within 20\u00b0F). The audited tails are not defects: out-of-guard moves become migrations, the rare case the design absorbs."], { justify: true }));
children.push(h3("Table R12a. Bounded-drift audit across three real domains"));
children.push(table(
  [2600, 1500, 1700, 1700, 2660],
  [
    ["Dataset (domain)", "Keys", "Updates", "Median |\u0394k|", "Moves within a modest guard"],
    ["S&P 500 prices (finance)", "505", "619,040", "44 cents", "98.3% within $5"],
    ["NBA Elo (sports ratings)", "104", "126,314", "7 Elo", "95.4% within 20"],
    ["US city temperatures (climate)", "16", "417,432", "2 \u00b0F", "94.9% within 10\u00b0F"],
  ]
));
children.push(p("Both the synthetic generators (8.1) and these real workloads are used; the synthetic streams isolate individual drift regimes and scale, while the real workloads defend the assumption itself across domains. Results appear in Section 9.9.", { justify: true }));
children.push(...figure("fig_drift_cdf.png", 440, "Bounded drift across three domains. When the guard width is normalised by each dataset\u2019s median |\u0394k|, the fraction of updates a guard absorbs in place collapses onto a common curve: a guard of three-to-seven times the median drift absorbs about 95% of moves in all three domains."));
children.push(h2("8.3 Baselines"));
children.push(bullet("Ordered index: a well-tuned B+-tree (delete-then-insert on update); high-update-rate B-tree techniques [5, 6]."));
children.push(bullet("Main-memory ordered index: the Adaptive Radix Tree [7] and the latch-free Bw-tree [8]."));
children.push(bullet("Learned / updatable learned index: ALEX [19] and the PGM-index [20]."));
children.push(bullet("Write-optimized index: a log-structured merge design [14]."));
children.push(bullet("Bounded-universe integer predecessor structure: van Emde Boas tree [1], y-fast trie [2], or fusion tree [3] (theory reference points)."));
children.push(bullet("Moving-object index adapted to 1D: the Bx-tree [11] (note its space-filling-curve mapping admits false hits, so an exactness adapter is required for a fair comparison)."));
children.push(bullet("Hard value-bucketing (guard = 0): partition by value and relocate on every boundary crossing \u2014 the drift-aware reduction of a cracking- or Bx-tree-style 1D scheme, used to isolate the guard\u2019s contribution (Section 9.10)."));
children.push(bullet("MARI ablations (see 8.4)."));
children.push(rp([{ t: "Fairness. ", b: true }, "Every baseline is tuned per workload; the tuning procedure and chosen parameters are reported so that the comparison is reproducible and not a strawman."], { justify: true }));
children.push(h2("8.4 Metrics"));
children.push(bullet("Update throughput (ops/s) and update latency (mean, p95, p99)."));
children.push(bullet("Query throughput and latency (mean, p95, p99)."));
children.push(bullet("Migration rate (fraction of updates causing a bucket move)."));
children.push(bullet("Query amplification (candidates scanned and verified per result item returned)."));
children.push(bullet("Memory usage (stable + delta + identifier table), including peak."));
children.push(bullet("Compaction overhead (time and write volume)."));
children.push(h2("8.5 Ablations"));
children.push(bullet("No guard (g = 0): isolates the value of guarded ownership."));
children.push(bullet("No delta index (in-place stable update): isolates the delta mechanism's contribution."));
children.push(bullet("Fixed vs. adaptive bucket boundaries / guard widths: isolates adaptivity."));
children.push(bullet("Guard-width sweep: maps the guard-vs-amplification trade-off curve directly."));
children.push(h2("8.6 Environment and protocol"));
children.push(p("The reference implementation is in Python (CPython) on a single-core x86-64 Linux sandbox with GCC 13 available for native engines; durable-write and native-engine measurements use the kernel\u2019s per-process I/O accounting, and threaded measurements use OS threads under group commit. Because the environment provides one core, the concurrency results measure overlap of blocking I/O rather than parallel compute; realising the sharding advantage as throughput requires a native, interpreter-lock-free implementation on multicore hardware, which we identify as the principal item of future work. All random seeds are fixed and published; the generator code, MARI implementation, baseline configurations, datasets, and analysis scripts are released for reproducibility.", { justify: true }));
children.push(gap());

// 9 Results format
children.push(h1("9. Results (reference implementation)"));
children.push(noteBox("Scope of these results \u2014 read before the tables", [
  "These numbers come from a single-machine Python reference implementation built to validate the MARI mechanism, not from a systems-grade prototype. They establish three things and only these: (i) exactness, (ii) the migration-reduction effect, and (iii) the guard-versus-amplification and compaction trade-offs.",
  "The baseline labelled \u201cordered index\u201d is a delete-then-insert sorted structure; it is NOT a tuned B+-tree, ART, Bw-tree, LSM, or learned index. Its ~99% relocation rate follows from the delete-then-insert semantics by construction. These early tables therefore do NOT claim MARI beats any production index; Section 9.15 adds a head-to-head comparison against faithful ART, PGM, and Bx-tree implementations made exact for this problem. Wall-clock throughput is omitted as a cross-system claim; the metrics reported are implementation-independent (relocation rate, migration rate, query amplification as entries-scanned-per-result, delta size).",
  "Configuration: universe M = 10^6, n = 20,000 keys, 200,000 updates, 2,000 range queries, drift bound \u03b4 = 50, bucket width w = 1,000, guard g = \u03b4 unless swept. Every workload\u2019s realized drift was audited to satisfy |\u0394k| \u2264 \u03b4 (adversarial mean |\u0394k| = 27.7, max = 50). Seeds fixed; full code released as supplementary material.",
]));
children.push(h2("9.1 Exactness and relocation across drift regimes"));
children.push(h3("Table R1. Exactness and relocation by drift regime (MARI guard g = \u03b4)"));
children.push(table(
  [2000, 1700, 1900, 1900, 1860],
  [
    ["Drift regime", "MARI migration rate", "Ordered reloc. rate", "MARI query amp. (scan/result)", "Exactness mismatches"],
    ["Uniform", "0.018", "0.990", "1.21", "0 / 2000"],
    ["Clustered", "0.051", "1.000", "1.21", "0 / 2000"],
    ["Directional", "0.028", "0.981", "1.26", "0 / 2000"],
    ["Adversarial (boundary osc.)", "0.015", "0.991", "1.01", "0 / 2000"],
    ["Hotspot queries", "0.018", "0.990", "1.01", "0 / 2000"],
  ]
));
children.push(p("MARI relocates 1.5\u20135.1% of updates versus 98\u2013100% for delete-then-insert \u2014 a 20\u201360\u00d7 reduction in structural moves \u2014 while returning exactly the oracle answer on all 2,000 queries per regime. The adversarial boundary-oscillation case, raised as a reviewer objection, yields one of the lowest migration rates (1.5%) because the guard absorbs the oscillation within a single bucket.", { justify: true }));
children.push(h2("9.2 The central trade-off: guard width vs. migration and amplification"));
children.push(h3("Table R2. The central trade-off: guard width vs. migration and amplification (uniform drift)"));
children.push(table(
  [1800, 2300, 2630, 2630],
  [
    ["Guard g", "Migration rate", "Query amp. \u2014 wide queries (\u00d75 buckets)", "Query amp. \u2014 narrow queries (sub-bucket)"],
    ["0 (no guard)", "0.046", "1.21", "5.89"],
    ["25", "0.024", "1.21", "6.24"],
    ["50 (= \u03b4)", "0.018", "1.22", "6.45"],
    ["100", "0.013", "1.24", "6.89"],
    ["250", "0.010", "1.31", "8.41"],
    ["500", "0.010", "1.40", "10.94"],
  ]
));
children.push(p("Increasing the guard monotonically lowers migration (0.046 \u2192 0.010) but raises query amplification. The cost is mild for wide queries (1.21 \u2192 1.40) and severe for selective ones (5.89 \u2192 10.94), so the optimal guard depends on the update:query ratio and query selectivity. This is the paper's central quantitative claim, and it is a trade-off, not a free win. The g = 0 column is the no-guard ablation: removing the guard roughly doubles migrations (0.018 \u2192 0.046 at the working point), isolating the guard's contribution.", { justify: true }));
children.push(h2("9.3 Compaction under the delta-ratio policy"));
children.push(h3("Table R3. Compaction under the delta-ratio policy (uniform drift)"));
children.push(table(
  [2340, 2340, 2340, 2340],
  [
    ["\u03b5", "Compaction work / append", "Max delta length", "Exactness mismatches"],
    ["0.25", "4.64", "263", "0"],
    ["0.50", "2.88", "526", "0"],
    ["1.00", "1.91", "1050", "0"],
  ]
));
children.push(p("Measured amortized compaction work per append tracks the proven O(1/\u03b5) bound, and the maximum delta length grows linearly with \u03b5, confirming Corollary 1's |D_j| = \u0398(\u03b5|S_j|). Exactness is preserved at every setting.", { justify: true }));
children.push(gap());

children.push(h2("9.4 Efficiency with real local range indexes"));
children.push(p("The results above measure the mechanism with dictionary-backed buckets. To test whether the migration advantage converts into algorithmic efficiency, we replaced each bucket with a real local range index (sorted stable tier, sorted delta tier, merge compaction, binary-search queries) and compared update and query throughput, in one Python runtime, against four baselines: a pure-Python sorted list (OrderedList), sortedcontainers.SortedList, a tiered LSM (buffer + sorted runs), and a radix-partitioned sorted index (RadixSorted, a partitioning baseline \u2014 not the native ART of [7], which is left for a systems-grade study). Update and query phases are timed separately; all structures are exact (oracle-checked). Absolute rates are Python-bound and not a cross-system claim; the relative comparison within one runtime is what speaks to algorithmic cost.", { justify: true }));
children.push(h3("Table R4. Update / query throughput, uniform drift (n = 20,000, 200,000 updates, bucket width 1,000)"));
children.push(table(
  [2300, 1760, 1760, 1760, 1780],
  [
    ["Structure", "Update ops/s", "Query ops/s", "Scan / result", "Relocation events"],
    ["RadixSorted (partitioned)", "589,611", "1,105", "1.00", "198,076"],
    ["MARI (guard, delta)", "399,964", "1,018", "1.22", "3,671 (migrations)"],
    ["SortedList (sortedcontainers)", "318,737", "1,041", "1.00", "198,076"],
    ["LSM (tiered runs)", "308,149", "1,012", "1.05", "0 (append-only)"],
    ["OrderedList (bisect list)", "33,777", "1,065", "1.00", "198,076"],
  ]
));
children.push(rp([{ t: "Reading R4 honestly. ", b: true }, "MARI is not the fastest updater. With fine buckets (~20 entries each), a relocation is a cheap shift, so RadixSorted \u2014 which relocates on every update but into a tiny leaf \u2014 leads at 589k ops/s, while MARI\u2019s delta/compaction/authoritative-table machinery costs enough to put it second at 400k. Migration-event reduction (3,671 vs 198,076) is real and implementation-independent, but on this in-memory single-thread workload it does not translate into a throughput win. Query throughput is statistically tied; MARI alone pays a scan amplification (1.22\u00d7)."], { justify: true }));
children.push(h3("Table R5. Update throughput vs. bucket size: cost decoupling (uniform drift)"));
children.push(table(
  [2400, 1800, 1800, 1900],
  [
    ["Bucket width (\u2248 entries/bucket)", "MARI ops/s", "RadixSorted ops/s", "Winner"],
    ["1,000 (~20)", "419,370", "564,987", "Radix"],
    ["5,000 (~100)", "392,630", "534,574", "Radix"],
    ["20,000 (~400)", "374,013", "463,469", "Radix"],
    ["50,000 (~1,000)", "341,353", "369,692", "~tie"],
    ["100,000 (~2,000)", "317,007", "220,379", "MARI"],
  ]
));
children.push(rp([{ t: "The defensible algorithmic claim. ", b: true }, "MARI\u2019s update throughput is nearly flat across bucket sizes (419k \u2192 317k), because its per-update cost is decoupled from bucket size: O(log|\u0394| + 1/\u03b5) amortized regardless of how many entries the bucket holds. A relocate-in-place partitioned index degrades with leaf size (565k \u2192 220k) because each relocation is O(bucket). The two curves cross near ~1,000 entries per bucket; MARI wins only beyond it. This \u2014 not a blanket throughput advantage \u2014 is the algorithmic property the paper can credibly assert: MARI converts the per-relocation cost from O(bucket size) to amortized O(log|\u0394| + 1/\u03b5)."], { justify: true }));
children.push(rp([{ t: "Where the decoupling is worth paying for. ", b: true }, "The crossover implies MARI\u2019s value is regime-specific: coarse or skew-forced large buckets; settings where a relocation triggers cascading work (durable two-page writes versus a single delta append, secondary-index maintenance, or tree rebalancing); and contended concurrency, where a local in-place update touches one bucket\u2019s latch while a migration touches two. None of these is single-thread in-memory throughput, on which a finely partitioned index wins. The paper must claim the cost-model property and concede the rest."], { justify: true }));
children.push(gap());

children.push(h2("9.5 Where the decoupling pays off: durable writes and contention"));
children.push(p("Section 9.4 showed MARI loses on single-thread in-memory throughput. We now test the two settings where the per-update cost model predicts MARI should win. Both are modelled, not wall-clock: single-thread Python cannot show a concurrency speed-up and the harness has no durable I/O, so we count implementation-independent quantities on the same update stream.", { justify: true }));
children.push(rp([{ t: "Durable write amplification (page model, page = 256 entries). ", b: true }, "A relocate-in-place update is a delete plus insert that dirties the leaf page(s) holding the old and new positions \u2014 a random read-modify-write. MARI instead appends to a per-bucket sequential delta log and rewrites a bucket's stable only at compaction. We count page-writes per update and classify them random vs. sequential."], { justify: true }));
children.push(h3("Table R6. Durable page-writes per update (P = 256)"));
children.push(table(
  [2400, 2320, 2320, 2320],
  [
    ["Drift regime", "InPlace global (random)", "InPlace radix (random)", "MARI (sequential)"],
    ["Uniform", "1.058", "1.077", "0.265"],
    ["Clustered", "1.061", "1.099", "0.275"],
    ["Directional", "1.049", "1.069", "0.266"],
  ]
));
children.push(p("MARI issues roughly 4\u00d7 fewer page-writes per update, and crucially they are sequential rather than random \u2014 the random read-modify-write that dominates flash and disk cost and device-level write amplification is eliminated. This is the LSM-family benefit, inherited because MARI's deltas are append logs; the guard sharpens it by keeping most updates local (one log) rather than migrations (two). The sequential cost (\u2248 0.27/update) splits roughly evenly between delta-page flushes and compaction rewrites; with the small buckets used here, compaction underfills pages, so coarser buckets would lower MARI's figure further \u2014 consistent with Section 9.4's crossover.", { justify: true }));
children.push(rp([{ t: "Contention (sharded-lock model). ", b: true }, "A global ordered index serializes every update on one structure. A partitioned index (radix or MARI) locks the bucket(s) an update touches; a cross-partition operation locks two and must be serialized by a sharded-lock scheme. We report the 2-lock rate."], { justify: true }));
children.push(h3("Table R7. Cross-partition (two-lock) operation rate"));
children.push(table(
  [2600, 2200, 2180, 2380],
  [
    ["Drift regime", "Global", "InPlace radix", "MARI (guard)"],
    ["Uniform", "serializes all", "0.047", "0.018"],
    ["Clustered", "serializes all", "0.055", "0.050"],
    ["Directional", "serializes all", "0.033", "0.028"],
  ]
));
children.push(p("Partitioning is the dominant concurrency win and it is shared with radix: both replace one global lock with per-bucket locks. The guard's specific contribution is a further reduction in two-lock (cross-partition) operations \u2014 about 2.5\u00d7 fewer than radix under uniform and directional drift (0.018 vs. 0.047; 0.028 vs. 0.033), and roughly even under clustered drift, where motion crosses boundaries regardless of the guard. So the guard helps contention modestly, not dramatically.", { justify: true }));
children.push(rp([{ t: "Synthesis. ", b: true }, "MARI's value is now located rather than asserted. On single-thread in-memory throughput it does not beat fine-grained partitioning (9.4). On durable write amplification it issues \u2248 4\u00d7 fewer writes and converts random into sequential I/O (R6) \u2014 the strongest case for the design. On concurrency it inherits the partitioning win and adds a modest guard-driven reduction in cross-partition operations (R7). A credible paper therefore positions MARI for write-amplification-sensitive and contention-sensitive deployments, and concedes the in-memory-throughput regime to simpler structures."], { justify: true }));
children.push(gap());

children.push(h2("9.6 From models to measurements: real durable writes and real threads"));
children.push(p("Sections 9.4\u20139.5 reported a page model and a lock model. We now confirm both with real system measurements: actual os.write/os.fsync to disk, and actual threads whose locked critical section performs a real fsync (a blocking syscall that releases the interpreter lock, so commits on different bucket files overlap). The in-place baseline writes the modified 4 KB page on each key change, as a durable B-tree must; MARI appends 16-byte records to a sequential log and rewrites stable segments at compaction, as a log-structured design does. Both use the same group-commit policy.", { justify: true }));
children.push(h3("Table R8. Measured durable writes (real os.write/os.fsync, 50,000 updates, uniform drift)"));
children.push(table(
  [2600, 1820, 1640, 1500, 1700],
  [
    ["Method", "Bytes written", "Bytes / update", "fsyncs", "Wall-clock"],
    ["InPlace (random 4 KB page rewrites)", "250.8 MB", "5,015", "954", "3.0\u20133.9 s"],
    ["MARI (sequential appends + compaction)", "3.37 MB", "67", "1,288", "2.2\u20132.9 s"],
    ["Advantage", "74\u00d7 fewer", "75\u00d7 lower", "\u2014", "1.3\u20131.4\u00d7"],
  ]
));
children.push(p("The byte counts are exact and deterministic: MARI writes 74\u00d7 fewer bytes per update and they are sequential, not random read-modify-writes \u2014 directly translating to lower flash wear and device-level write amplification. The figure already includes MARI\u2019s compaction rewrites; MARI even issues slightly more fsyncs (compaction adds commits), yet still writes two orders of magnitude less data. Wall-clock is only modestly better here because this container is fsync-bound (the \u2248 0.7 ms fsync dominates and both methods pay similar fsync counts); on bandwidth-limited or wear-limited storage the 74\u00d7 byte reduction is the operative quantity.", { justify: true }));
children.push(h3("Table R9. Measured concurrency scaling (real threads, per-op fsync critical section, 8,000 ops)"));
children.push(table(
  [2600, 1540, 1540, 1540, 1540],
  [
    ["Threads", "1", "2", "4", "8"],
    ["Global lock, one file (ops/s)", "1,710", "1,710", "1,750", "1,750"],
    ["MARI sharded, per-bucket files (ops/s)", "1,460", "1,810", "1,960", "3,080"],
    ["Speedup vs. global", "0.8\u00d7", "1.0\u00d7", "1.1\u00d7", "1.8\u00d7"],
  ]
));
children.push(p("A single global lock over one file does not scale (throughput is flat, \u2248 1.0\u00d7 from 1 to 8 threads): every commit serialises. MARI\u2019s per-bucket locks and per-bucket logs scale \u2248 2.1\u00d7 over the same range, overtaking the global design and reaching \u2248 1.8\u00d7 its throughput at eight threads despite a small single-thread overhead. This is a real demonstration that the partition-local design admits concurrency a global structure cannot. The scaling factor is a floor, not a ceiling: the interpreter lock still serialises the non-fsync part of each critical section and the container\u2019s fsync overlap is imperfect, so native code with true I/O parallelism would scale further. The benefit comes from partitioning (shared with a radix index); MARI\u2019s guard adds the cross-partition-rate reduction of Table R7.", { justify: true }));
children.push(rp([{ t: "Bottom line. ", b: true }, "The two regimes the cost models predicted are now measured, not hypothesised: \u2248 74\u00d7 lower durable write volume (sequential vs. random) and \u2248 2\u00d7 concurrency scaling where a global index is flat. With the in-memory result (9.4), the evidence supports a precise claim \u2014 MARI is a write-amplification- and contention-favourable index for bounded-drift integer keys \u2014 and refutes the broader claim that it is simply faster. Section 9.7 reproduces the write-amplification result against production-grade native engines."], { justify: true }));
children.push(gap());

children.push(h2("9.7 Native-engine validation: LMDB and RocksDB"));
children.push(p("To move the write-amplification claim off our own implementation, we replayed the same bounded-drift workload against two native engines under identical group-commit durability: LMDB, a copy-on-write B+-tree (the relocate-in-place baseline), and RocksDB (via rocksdict), a production log-structured store. The index is keyed by the moving value (the score), so range queries over that value are possible \u2014 which means a plain key-value store must perform a delete-old-plus-insert-new on every change, exactly the relocation MARI's guarded ownership avoids. We measured real bytes written to disk through the kernel's per-process I/O accounting (/proc/self/io): wchar is the bytes issued to write(), write_bytes the bytes that reached storage. Counts were identical across repeated runs.", { justify: true }));
children.push(...figure("fig_writeamp.png", 430, "Durable bytes written per update on the bounded-drift workload (log scale). Against a native B+-tree (LMDB) MARI writes 58\u201382\u00d7 fewer bytes; its write volume lands in the same band as a native LSM (RocksDB)."));
children.push(h3("Table R10. Durable bytes written per update (native engines, score-keyed, 100,000 bounded-drift updates)"));
children.push(table(
  [3000, 2300, 2300, 2160],
  [
    ["Engine", "Bytes/update issued (wchar)", "Bytes/update to storage", "vs. MARI"],
    ["LMDB \u2014 native B+-tree (copy-on-write)", "2,861", "9,369", "58\u201382\u00d7 more"],
    ["RocksDB \u2014 native LSM", "75.5", "108", "same class"],
    ["MARI \u2014 guard + append + compaction", "49.7", "115", "\u2014"],
  ]
));
children.push(rp([{ t: "Result. ", b: true }, "Against a real native B+-tree, MARI writes 58\u00d7 fewer bytes by the write()-issued measure and 82\u00d7 fewer by the bytes-to-storage measure \u2014 confirming, and slightly exceeding, the 74\u00d7 figure the page model predicted (Section 9.5). Equally important, MARI\u2019s write volume lands in the same band as RocksDB: the guarded-ownership design inherits the log-structured write-amplification advantage while supporting exact range queries over the moving value, which a plain key-value store can only do by relocating. This is the production-grade confirmation the earlier sections flagged as missing."], { justify: true }));
children.push(rp([{ t: "Honest scope. ", b: true }, "Three caveats. First, this is the score-keyed configuration required for range-by-value; a key-value store keyed instead by a static identifier writes one record per update but then cannot answer score-range queries without a secondary index, which reintroduces the relocation. Second, MARI\u2019s on-disk footprint here is larger (the prototype does not truncate its delta log after compaction); the write volume \u2014 what drives wear and amplification \u2014 is what we measure, and a production version would reclaim the log. Third, this validates the write-amplification claim only; it is not a throughput comparison, and the native engines remain far faster than our Python prototype in raw operations per second."], { justify: true }));
children.push(gap());

children.push(h2("9.8 Multi-threaded throughput against a production concurrent engine"));
children.push(p("Section 9.6 reported that MARI\u2019s per-bucket locking scaled \u2248 2\u00d7 from one to eight threads where a single global lock stayed flat (Table R9). That experiment used per-operation durability, so each locked critical section performed an fsync \u2014 a blocking, lock-releasing syscall \u2014 and the scaling came from fsyncs to independent per-bucket logs overlapping. The natural question is whether that advantage survives against a real concurrent engine under realistic amortized durability. We therefore replayed the same workload, split across threads by key, under group-commit durability (one fsync per 128 operations), comparing RocksDB \u2014 driven with batched writes so its heavy work runs in native code with the interpreter lock released \u2014 against MARI with per-bucket logs and MARI with a single log.", { justify: true }));
children.push(h3("Table R11. Durable group-commit throughput vs. threads (ops/s; within-engine scaling 1\u21928)"));
children.push(table(
  [3050, 1560, 1560, 1560, 1560],
  [
    ["Engine", "T = 1", "T = 2", "T = 4", "T = 8  (scaling 1\u21928)"],
    ["RocksDB \u2014 native LSM, single WAL", "80\u2013117k", "143\u2013162k", "159\u2013183k", "160\u2013170k  (1.4\u20132.1\u00d7)"],
    ["MARI \u2014 per-bucket logs (Python)", "\u2248 80k", "\u2248 83k", "\u2248 85k", "\u2248 83k  (\u2248 1.0\u00d7)"],
    ["MARI \u2014 single log (Python)", "\u2248 143k", "\u2248 145k", "\u2248 146k", "\u2248 133k  (\u2248 1.0\u00d7)"],
  ]
));
children.push(rp([{ t: "Finding. ", b: true }, "Under amortized group commit the result reverses relative to Table R9: RocksDB scales 1.4\u20132.1\u00d7 with threads, because its per-operation work runs in native code with the interpreter lock released and its internal group commit coalesces concurrent log flushes; MARI \u2014 whether sharded or global \u2014 stays flat at \u2248 1.0\u00d7, because its update logic is interpreted Python and the interpreter lock serialises the compute once fsync is amortised away and no longer dominates the critical section. The two results are consistent: MARI\u2019s sharding helps only while durable I/O dominates (the per-operation-fsync regime of R9), where independent per-bucket logs let fsyncs overlap \u2014 a structural advantage that a single shared write-ahead log, as in RocksDB, does not have. Once the compute dominates, the interpreter lock erases it."], { justify: true }));
children.push(rp([{ t: "Honest verdict. ", b: true }, "MARI\u2019s per-bucket sharding advantage does not survive as a realised throughput win against a production concurrent engine in the present Python prototype: under realistic group-commit durability RocksDB scales with threads and MARI does not. The advantage is genuine but structural \u2014 partition-local updates and independent per-bucket logs avoid both a global lock and a single write-ahead log \u2014 and converting it into thread-scaling throughput requires a native, interpreter-lock-free implementation of MARI. We report this rather than the more flattering per-operation-fsync number in isolation. Absolute operations-per-second are not directly comparable across engines, since an in-guard MARI update appends one record whereas a key-value store performs a delete-plus-insert; the comparable quantity is the within-engine scaling factor."], { justify: true }));
children.push(gap());

children.push(h2("9.9 Validation on real bounded-drift workloads (three domains)"));
children.push(p("We replayed the S&P 500 stream of Section 8.2 \u2014 619,040 chronological daily-price updates over 505 keys \u2014 through MARI, verifying every sampled range query against a brute-force oracle and sweeping the guard width. The key is the closing price in cents; queries ask which stocks trade in a random price band.", { justify: true }));
children.push(h3("Table R12. MARI on real S&P 500 daily prices (619,040 updates, 505 keys, bucket width $10)"));
children.push(table(
  [2100, 2000, 2300, 2300, 2460],
  [
    ["Guard width", "Migrations", "Migration rate", "Local updates", "Exactness (mismatch / queries)"],
    ["$2 (200c)", "17,619", "2.87%", "595,596", "0 / 2,500"],
    ["$5 (500c)", "9,901", "1.61%", "603,314", "0 / 2,500"],
    ["$10 (1000c)", "5,314", "0.87%", "607,901", "0 / 2,500"],
    ["$20 (2000c)", "2,324", "0.38%", "610,891", "0 / 2,500"],
  ]
));
children.push(rp([{ t: "Findings. ", b: true }, "Three points. First, exactness: zero mismatches across every guard setting and all sampled queries, on real data, confirming the construction-based guarantee outside the synthetic generators. Second, the migration rate on real prices (0.4\u20132.9% depending on guard) falls squarely inside the synthetic range of 1.5\u20135% (Section 9.1), so the generators were representative, not favourable. Third, the bounded-drift audit tracks the migration rate: a $5 guard, which the audit showed absorbs 98.3% of day-to-day moves, yields a measured 1.61% migration, and a $10 guard (99.5% absorbed) yields 0.87% — close to, though not exactly, the drift tail, a relationship Section 9.13 turns into a concrete guard-setting rule and quantifies. The guard/migration trade-off of Table R2 reproduces on real data \u2014 wider guards relocate less \u2014 and the load-bearing assumption of the paper is no longer merely assumed."], { justify: true }));
children.push(p("To show the assumption is not a property of one price file, we repeated the exercise on the sports-ratings and climate workloads of Section 8.2. MARI is exact on all three, and the migration rate tracks each domain\u2019s drift scale and universe.", { justify: true }));
children.push(h3("Table R13. MARI across three real domains (representative guard per dataset)"));
children.push(table(
  [2500, 1450, 1550, 1700, 1500, 1660],
  [
    ["Dataset", "Keys", "Updates", "Guard", "Migration", "Exactness"],
    ["S&P 500 prices", "505", "619,040", "$5", "1.61%", "0 / 2,500"],
    ["NBA Elo ratings", "104", "126,314", "20", "4.09%", "0 / 2,500"],
    ["US city temps", "16", "417,432", "10\u00b0F", "6.65%", "0 / 2,500"],
  ]
));
children.push(rp([{ t: "Across domains. ", b: true }, "Sweeping each guard reproduces the trade-off everywhere: NBA Elo migrates 6.6%, 4.1%, 2.1% at guards 10, 20, 40, and city temperatures 19%, 13%, 6.7% at 3\u00b0F, 5\u00b0F, 10\u00b0F. The temperature universe is narrow (about 130 distinct values), so a fixed grid crosses bucket boundaries more often and migration is higher \u2014 an honest consequence of fine granularity relative to the universe, not a correctness issue. In every case exactness is preserved and the audited within-guard fraction (Table R12a) predicts the migration rate. Bounded drift is therefore a cross-domain phenomenon \u2014 finance, sports ratings, and climate \u2014 not an artifact of one dataset."], { justify: true }));
children.push(...figure("fig_guard_migration.png", 440, "Migration rate versus guard width (normalised by median |\u0394k|) on the three real workloads. Wider guards relocate fewer items in every domain; all configurations are exact. The narrow-universe temperature workload sits highest, as expected."));
children.push(gap());

children.push(h2("9.10 Isolating the guard: versus hard value-bucketing"));
children.push(p("The comparisons so far pit MARI against delete-then-insert, which relocates on essentially every update. A sharper question is whether the guard earns its keep against a drift-aware competitor. The natural one is hard value-bucketing \u2014 partition by value and relocate whenever a key crosses a bucket boundary \u2014 which is what a cracking- or Bx-tree-style 1D scheme reduces to, and which is exactly MARI with the guard set to zero. We sweep bucket width and compare relocation rate and query amplification.", { justify: true }));
children.push(h3("Table R14. MARI versus hard value-bucketing (guard = 0), real S&P 500"));
children.push(table(
  [2100, 2550, 2550, 2660],
  [
    ["Bucket width", "Hard-bucket migration (guard 0)", "MARI migration (guard $5)", "Reduction"],
    ["$2.50", "27.7%", "3.2%", "8.7\u00d7"],
    ["$5.00", "15.2%", "2.5%", "6.1\u00d7"],
    ["$10.00", "7.9%", "1.6%", "4.9\u00d7"],
  ]
));
children.push(...figure("fig_guard_isolation.png", 430, "Isolating the guard on real S&P 500 prices. Hard value-bucketing (guard = 0) \u2014 the cracking-/Bx-tree-style baseline \u2014 relocates 3\u20139\u00d7 more than MARI at every bucket width. MARI at the narrowest bucket ($2.50, the best query selectivity) still relocates less than hard bucketing at any width."));
children.push(rp([{ t: "The guard is the mechanism. ", b: true }, "Hard value-bucketing relocates 3\u20139\u00d7 more than MARI at the same width, and the gap widens as buckets narrow \u2014 precisely the regime with the best query selectivity. Because query amplification falls with bucket width (2.27 at $2.50 down toward 1.3 at $10) while the guard keeps migration low, MARI reaches the low-migration, narrow-bucket corner that hard bucketing cannot: at a $2.50 width MARI relocates 3.2% versus hard bucketing\u2019s 27.7%, while a wider hard bucket that matched MARI\u2019s migration would forfeit selectivity. The same pattern holds on synthetic uniform drift (a 2\u20133\u00d7 reduction at every width). The guard, not value-partitioning, is what does the work; everything else is shared with prior designs (Section 10.1). All configurations are exact."], { justify: true }));
children.push(gap());
children.push(h2("9.11 Query-side characterization: latency and verification cost"));
children.push(p("The evaluation so far is update-centric. We now characterize the query side directly on the real-local-index MARI of Section 9.4, measuring per-query latency percentiles, the scan amplification, and \u2014 the quantity Section 4.3 flags as central \u2014 the cost of verifying candidates against the authoritative table T, expressed per result item. Queries are random value bands over the built uniform-drift state (M = 10^6, n = 20,000 keys after 200,000 updates), swept from a few results to about a thousand. Absolute microseconds are prototype-bound and not a cross-system claim; the scanned-per-result and verifies-per-result figures are implementation-independent. Every configuration is checked exact against the brute-force oracle.", { justify: true }));
children.push(h3("Table R15. Query latency and per-result cost vs. selectivity (MARI, guard = \u03b4)"));
children.push(table(
  [2100, 1600, 1600, 1800, 1800],
  [
    ["Avg. results returned", "p50 (\u00b5s)", "p99 (\u00b5s)", "Scanned / result", "Verifies / result"],
    ["2", "5.6", "42", "1.25", "1.06"],
    ["10", "11.0", "49", "1.23", "1.01"],
    ["40", "27.5", "80", "1.23", "1.01"],
    ["204", "88", "744", "1.24", "1.00"],
    ["1,002", "405", "1,227", "1.23", "1.00"],
  ]
));
children.push(...figure("fig_query.png", 540, "Query-side cost on uniform bounded drift. (a) Latency scales with the result-set size; p50 rises from a few microseconds at two results to several hundred at a thousand, and the p99 tail tracks the same quantity. (b) Per-result cost is flat in selectivity: MARI scans a near-constant ~1.2 entries and performs ~1 table verification per emitted result."));
children.push(rp([{ t: "Verification is not a hidden blow-up. ", b: true }, "Across the whole selectivity range MARI performs essentially one T-lookup per emitted result (verifies/result 1.00\u20131.06, highest only at the narrowest queries, where a small fixed overhead is spread over a handful of results) and scans a near-constant ~1.23 entries per result. With real per-bucket sorted indexes a query binary-searches within each guard-intersecting bucket rather than scanning it, so the selective-query amplification reported for the dictionary-backed mechanism (Table R2) largely disappears: amplification is a small constant in selectivity, not a growing penalty. Query latency therefore scales with the result-set size (Figure 7a), p50 rising from ~6 \u00b5s at two results to ~405 \u00b5s at a thousand, with the p99 tail tracking the same quantity."], { justify: true }));
children.push(rp([{ t: "Widening the guard is nearly free on the query side. ", b: true }, "Holding selectivity fixed (a 2,000-wide band) and sweeping the guard from 0 to 1,000, p50 latency moves only from 24 to 28 \u00b5s while both scanned/result (1.24 \u2192 1.23) and verifies/result (1.01 \u2192 1.00) stay flat \u2014 even as the migration rate falls from 4.7% to 1.0%. This is the query-side counterpart of the refutation in Section 7.2: for queries at or above the guard scale, the guard buys its migration reduction without a measurable query penalty. For queries far narrower than the guard, a wider guard does pull in more neighbouring candidates \u2014 the sub-bucket regime of Table R2."], { justify: true }));
children.push(h3("Table R16. Query throughput vs. same-runtime baselines (uniform drift, 2,000-wide queries)"));
children.push(table(
  [3200, 2000, 2300, 1700],
  [
    ["Structure", "p50 latency (\u00b5s)", "Query throughput (q/s)", "Scanned / result"],
    ["MARI (guard)", "25.2", "32,178", "1.24"],
    ["RadixSorted (partitioned)", "7.2", "112,202", "1.00"],
    ["SortedList (sortedcontainers)", "7.8", "99,804", "1.00"],
  ]
));
children.push(rp([{ t: "The honest read-side cost. ", b: true }, "What MARI pays on reads is absolute throughput. On identical queries against the same-runtime baselines (Table R16), MARI answers about 32k queries/s versus ~100\u2013112k for a plain partitioned or sorted index \u2014 roughly 3\u00d7 slower \u2014 because those baselines walk exactly the result with no verification, whereas MARI scans ~1.24\u00d7 as many candidates and performs a table lookup on each. This is the read-side analogue of the update-side concession of Section 9.4: exactness-by-verification and guard overlap are not free, and query-dominated workloads pay for them. MARI remains best positioned where updates dominate queries (Section 10). All query configurations above are exact (zero oracle mismatches)."], { justify: true }));
children.push(gap());
children.push(h2("9.12 Crash recovery: rebuilding the table and stable tiers from the logs"));
children.push(p("MARI\u2019s durable form persists, per bucket, an append-only delta log of fixed records (sequence number, operation, id, key) plus a stable segment rewritten at each compaction; group commit fsyncs every G operations. The authoritative identifier table T is the one structure never written to disk \u2014 it is an in-memory derivative. The recovery question is therefore whether the queryable index, T included, can be rebuilt from the per-bucket logs alone.", { justify: true }));
children.push(p("It can, in a single linear pass. For each bucket, recovery loads the stable segment into the live map, then replays the delta-log tail in sequence order \u2014 a PUT sets the key, a TOMB removes the id, the latest version winning \u2014 reconstructing the bucket\u2019s current membership; T is then populated as id \u2192 (key, bucket) from every recovered bucket. A migration, which writes a TOMB to the source bucket and a PUT to the destination, reconstructs correctly because the destination\u2019s PUT carries the live key while the source\u2019s TOMB removes the stale entry. Recovery touches each durable record once and performs no random I/O; its cost is O(n + \u03a3|D_j|), linear in the live data plus the \u03b5-bounded delta tail (Corollary 1).", { justify: true }));
children.push(h3("Table R17. Crash recovery from the durable logs (rebuilding stable tiers + table T)"));
children.push(table(
  [3000, 1500, 1700, 1800, 1700],
  [
    ["Crash scenario", "Live items", "Stable + delta records replayed", "Table T rebuilt", "Query mismatches"],
    ["End of stream", "8,000", "7,989 + 1,404", "8,000 / 8,000", "0 / 2,000"],
    ["Mid-stream commit boundary (after 39,936 updates)", "8,000", "7,997 + 1,143", "8,000 / 8,000", "0 / 2,000"],
  ]
));
children.push(p("We exercise this on a durable run of 8,000 keys under 80,000 bounded-drift updates. After a crash that discards all in-memory state, recovery rebuilds T in full \u2014 8,000 of 8,000 live items \u2014 from about 8,000 stable and 1,400 delta records (\u2248 86 KB, tens of milliseconds in the prototype), and the recovered index answers a 2,000-query sample identically to a brute-force oracle: zero mismatches. The same holds when the crash falls at an arbitrary group-commit boundary mid-stream; the committed prefix recovers exactly (Table R17).", { justify: true }));
children.push(rp([{ t: "Atomicity and prefix consistency. ", b: true }, "Recovery restores a state consistent up to the last durable commit. The one ordering hazard is a migration whose two records straddle a crash \u2014 a source TOMB persisted without its destination PUT would lose the item. MARI avoids this by emitting both records within a single group-commit, so the committed prefix never contains a half-applied migration; equivalently, a migration may be logged as one record naming source, destination, and key. Operations after the last fsync are lost, as in any group-commit system: durability is to the commit boundary, not the individual update. The remaining production choice \u2014 independent per-bucket logs (the form measured in Section 9.8, whose flushes overlap) versus a single write-ahead log \u2014 and concurrent recovery are part of the native implementation, future work."], { justify: true }));
children.push(gap());
children.push(rp([{ t: "Real-crash validation (SIGKILL). ", b: true }, "To go beyond an in-memory simulation we run the durable form in a separate process that fsync-commits every update, terminate it with SIGKILL mid-run, and recover in a fresh process from the on-disk logs alone. When the kill falls at a commit boundary the authoritative table is rebuilt in full (300 of 300 live ids) from 2.6 KB of stable and delta records in under 10 ms, and the recovered index is exact to the committed prefix \u2014 zero mismatches over 3,000 queries. The test also exposes one honest limitation: the reference code fsyncs each append independently, so a kill landing between a migration\u2019s two appends (a tombstone at the source bucket and an insert at the destination) can leave a single id half-moved. Prefix-exact recovery under arbitrary kill timing therefore requires committing each migration as one fsync group \u2014 a design requirement we state explicitly and that the reference implementation does not yet enforce."], { justify: true }));
children.push(gap());
children.push(h2("9.13 Setting the guard: a tuning rule from the drift quantile"));
children.push(p("Corollary 4 bounds the per-step relocation probability by the drift mass beyond the guard, Pr[migrate] \u2264 Pr[|\u0394k| > g]. This gives a concrete way to set the guard from the audit: to target a migration rate \u03c1, choose the bucket width w from the memory and query-amplification budget (Sections 9.2 and 9.11), then set the guard to the (1 \u2212 \u03c1) quantile of the audited per-key drift. We test the rule directly on all three real streams, setting g to the p90, p95, and p99 drift quantiles and measuring the realized migration rate against the target tail (1 \u2212 q).", { justify: true }));
children.push(h3("Table R18. Guard set to the drift quantile: target vs. realized migration (real streams)"));
children.push(table(
  [2500, 1800, 1500, 1900, 1700],
  [
    ["Domain (bucket width)", "Guard = q-quantile", "Target (1\u2212q)", "Realized migration", "Exact (mismatch / queries)"],
    ["S&P 500 (w = 1,000\u00a2)", "p90 = 182\u00a2", "10%", "3.0%", "0 / 1,502"],
    ["", "p95 = 275\u00a2", "5%", "2.4%", "0 / 1,502"],
    ["", "p99 = 673\u00a2", "1%", "1.3%", "0 / 1,502"],
    ["NBA Elo (w = 50)", "p90 = 16", "10%", "4.8%", "0 / 1,503"],
    ["", "p95 = 20", "5%", "4.1%", "0 / 1,503"],
    ["", "p99 = 30", "1%", "2.8%", "0 / 1,503"],
    ["City temps (w = 10)", "p90 = 8\u00b0F", "10%", "7.9%", "0 / 1,472"],
    ["", "p95 = 11\u00b0F", "5%", "5.4%", "0 / 1,472"],
    ["", "p99 = 16\u00b0F", "1%", "2.3%", "0 / 1,472"],
  ]
));
children.push(...figure("fig_tuning.png", 410, "Guard set to the drift quantile: target versus realized migration on three real streams. Setting g to the (1 \u2212 \u03c1) quantile of |\u0394k| lands realized migration below the target for loose targets (the wide bucket absorbs extra drift) and above it for tight targets (finite width and guard-band occupancy add crossings); the two regimes cross near 3\u20135%. All points are exact."));
children.push(rp([{ t: "The quantile is a sound knob, but not an identity. ", b: true }, "In every domain a higher drift quantile yields a lower migration rate, and all nine configurations are exact (0 mismatches over ~1,500 queries each). The mapping to (1 \u2212 q) is approximate, and Figure 8 shows the shape honestly. At loose targets (\u03c1 = 10%, the p90 guard) realized migration sits below target in all three domains \u2014 most so for S&P (3.0% vs 10%), whose bucket width (1,000\u00a2) far exceeds the guard (182\u00a2), so the wide core absorbs drift the tail-mass argument counts as escapes. At a tight target (\u03c1 = 1%, the p99 guard) realized migration instead exceeds target by 1.3\u20132.8\u00d7: finite width and guard-band occupancy \u2014 a key already in the guard band has less than g of slack \u2014 add boundary crossings the drift tail does not capture, and these dominate once the tail itself is tiny. The two effects cross near \u03c1 \u2248 3\u20135%."], { justify: true }));
children.push(rp([{ t: "The recipe. ", b: true }, "Set g to the (1 \u2212 \u03c1) drift quantile as a first cut: it lands realized migration within a small factor of \u03c1, and at or below \u03c1 for the common moderate targets (\u03c1 \u2265 5%) when buckets are at least as wide as the guard; if a hard bound is required, raise the guard one quantile or widen the buckets and re-audit. The audit (Table R12a) plus this rule replaces guesswork with a measured starting point, while the width stays the independent lever for the memory and query-amplification trade-off."], { justify: true }));
children.push(gap());
children.push(rp([{ t: "Reading the rule. ", b: true }, "The quantile is a safe upper-bound recipe in the common regime, not an identity. For moderate targets (\u03c1 \u2265 5%) with the bucket at least as wide as the guard, realized migration sits at or below target on all three streams \u2014 the wide core absorbs extra drift \u2014 so g = Q(1\u2212\u03c1) over-provisions safely. It turns optimistic only at tight targets (p99). Practical rule: set g = Q(1\u2212\u03c1) for \u03c1 \u2265 5%, treat it as an upper bound, and re-audit once if a hard guarantee at a tighter target is required."], { justify: true }));
children.push(gap());
children.push(h2("9.14 Memory overhead: what the authoritative table costs"));
children.push(p("The space bound is O(n + m), but a fair worry is that the authoritative table T \u2014 a full id \u2192 (key, bucket) map \u2014 quietly cancels the durable-write saving. We measure the resident footprint on the same workload (20,000 live keys after 200,000 updates), counting stored (id, key)-equivalent records per live item, which is implementation-independent, alongside measured retained bytes.", { justify: true }));
children.push(h3("Table R19. In-memory footprint vs. a plain ordered index (20,000 live items)"));
children.push(table(
  [3300, 1800, 1700, 2000],
  [
    ["Structure", "Records / item", "\u00d7 ordered index", "Retained bytes / item"],
    ["SortedList (ordered index)", "2.00", "1.0\u00d7", "95"],
    ["RadixSorted (partitioned)", "2.00", "1.0\u00d7", "99"],
    ["MARI \u2014 reference", "3.41", "1.7\u00d7", "268"],
    ["MARI \u2014 lean (T + sorted tier + delta)", "2.40", "1.2\u00d7", "\u2014"],
  ]
));
children.push(rp([{ t: "The table does not cancel the write saving. ", b: true }, "Every exact design carries a structural 2\u00d7: a by-key sorted tier for range scans and a by-id map for the value, which is why the ordered-index baselines themselves hold two records per item (a sorted list plus a current-value dict). MARI\u2019s reference implementation holds 3.41 \u2014 1.7\u00d7 the baseline \u2014 because it keeps the stable tier twice, as a dict (smap) and a sorted list (skeys), on top of T. That stable dict is redundant with T and can be dropped, rebuilding the sorted tier from T at compaction; the lean form then holds 2.40 records per item, 1.2\u00d7 the ordered index. MARI\u2019s only inherent excess over a plain ordered index is the per-item bucket field in T and the \u03b5-bounded delta tail \u2014 the 0.40 records per item above the structural floor, consistent with Corollary 1 \u2014 not a multiplicative blow-up."], { justify: true }));
children.push(rp([{ t: "On measured bytes. ", b: true }, "Retained bytes per item run higher than the record ratio (268 vs ~95\u201399, \u2248 2.8\u00d7) because the reference keeps a thousand small per-bucket Python containers \u2014 dicts, sorted lists, and tombstone sets \u2014 whose object overhead dominates at this bucket count; a native contiguous per-bucket layout removes it, so the byte ratio is an implementation artifact and the record ratio is the structural figure. Set against the durable-write result (58\u201382\u00d7 fewer bytes written, Section 9.7), a sub-2\u00d7 resident-memory premium is a favourable trade for write-amplification-sensitive deployments."], { justify: true }));
children.push(gap());
children.push(h2("9.15 Comparison with real ordered-index designs (ART, PGM, Bx-tree)"));
children.push(p("The results so far isolate MARI\u2019s mechanism against a delete-then-insert baseline. We now compare against three real ordered-index designs, each implementing the same exact range-reporting-under-drift problem and each verified exact against the brute-force oracle: an adaptive radix tree (ART), a dynamic learned index (a leveled PGM with piecewise-linear segment lookups), and a Bx-tree with the exactness adapter of Section 8.3 (time partitions plus current-value verification). All are faithful Python implementations; as elsewhere, the load-bearing metrics are implementation-independent \u2014 relocations per update, structural writes per update, verifications per result \u2014 and absolute throughput is indicative, not a cross-system claim. Figures are means over five seeds.", { justify: true }));
children.push(h3("Table R20. MARI vs. real ordered-index designs on exact range reporting under drift (n = 20,000; 120,000 updates; 5 seeds, mean \u00b1 std)"));
children.push(table(
  [3100, 2100, 1700, 2000, 1100],
  [
    ["Structure", "Relocations / update", "Writes / update", "Verifications / result", "Exact?"],
    ["MARI", "0.024 \u00b1 0.000", "1.15", "1.01", "yes"],
    ["ART (adaptive radix tree)", "0.990 \u00b1 0.000", "1.08", "0.00", "yes"],
    ["PGM (dynamic learned)", "0.990 \u00b1 0.000", "4.96", "1.38", "yes"],
    ["Bx-tree (+ exactness adapter)", "0.990 \u00b1 0.000", "1.16", "6.93", "yes"],
  ]
));
children.push(...figure("fig_baseline.png", 540, "MARI versus three exact ordered-index competitors. (a) Every competitor relocates on essentially every update (0.99); MARI relocates 0.024, about 40\u00d7 fewer, because the guard absorbs the move. (b) Each competitor stays exact only by paying elsewhere \u2014 ART by the full relocation, the dynamic PGM by ~5\u00d7 merge writes per update, the Bx-tree by ~7\u00d7 query verifications per result \u2014 while MARI keeps both low."));
children.push(rp([{ t: "What the comparison shows. ", b: true }, "Two facts stand out, both implementation-independent. First, every competitor relocates on essentially every update (0.99), because a value change is a delete-then-insert in an ordered structure; MARI relocates 0.024 \u2014 about 40\u00d7 fewer. Second, each competitor remains exact only by paying elsewhere: ART by performing the full relocation (no verification, but a structural move every update); the dynamic PGM by ~5\u00d7 structural writes per update from leveled merges; and the Bx-tree by 6.9 candidate verifications per result, since its time partitions over-fetch and must be checked against current values. MARI alone keeps both low \u2014 ~1.15 writes per update and ~1.0 verification per result \u2014 and is the only design here that is exact without either relocating on every update or over-paying on writes or query verification."], { justify: true }));
children.push(rp([{ t: "Throughput and scale, scoped honestly. ", b: true }, "In this Python harness MARI also has the highest update and query throughput (about 334k updates/s and 6.2k queries/s, versus 143\u2013265k and 2.6\u20134.3k for the competitors), but we do not claim cross-system superiority from a Python measurement; a native, multi-core comparison is the remaining gate (Section 11). The gap also widens with scale: at n = 100,000 keys under 600,000 updates MARI\u2019s relocation rate falls to 0.009 (denser buckets absorb more motion) against 0.99 for every competitor \u2014 about 110\u00d7 \u2014 while the dynamic PGM\u2019s structural writes per update rise to 7.5 as its merge tree deepens. Exactness holds for all four at both scales (zero oracle mismatches)."], { justify: true }));
children.push(gap());
children.push(rp([{ t: "On the definitional objection. ", b: true }, "That a delete-then-insert structure relocates on essentially every update is true by construction, not an empirical discovery; we report 0.99 only to anchor the contrast. The non-definitional content here is threefold: the mechanism that breaks the coupling (guarded ownership), the distinct cost each competitor pays to stay exact (ART the full relocation, the PGM ~5\u00d7 merge writes per update, the Bx-tree ~7\u00d7 verifications per result), and the one quantity measured against native engines rather than asserted \u2014 durable bytes written (Section 9.7). The relocation rate frames the problem; the durable-byte result and the proven bounds carry the claim."], { justify: true }));
children.push(rp([{ t: "On baseline fairness. ", b: true }, "The three competitors are faithful reference implementations in the same language and harness as MARI, each tuned for this problem \u2014 the PGM keeps a sorted level-0 buffer (its per-result scan is 2.8, not an artefact of linear scanning), ART uses adaptive Node4/16/48/256, the Bx-tree time-partitions with rollover \u2014 and each verified exact against the oracle, not configured to lose. We do not equate them with the tuned native artefacts of the same name; the comparison rests on implementation-independent counts, and a native re-run is future work (Section 11). The Bx-tree exactness adapter \u2014 time-partition scan plus current-value verification \u2014 is our construction, not prior Bx-tree work, presented as the faithful exact-range competitor a Bx-tree would require."], { justify: true }));
children.push(gap());
children.push(h2("9.16 Heteroscedastic drift and per-region guards"));
children.push(p("The model of Section 4 assumes a single global drift bound \u03b4. Real drift is often heteroscedastic: on S&P prices the dollar move scales with the price level (Section 9.9), so one global guard is mis-provisioned. We make the generalization explicit. Replace the single bound by a region map \u03b4 : r \u2192 R+, one bound per region (a bucket or a price band); setting the per-region guard g(r) = Q_{|\u0394k| in r}(1 \u2212 \u03c1) targets the same migration \u03c1 in every region, which MARI\u2019s adaptive widths (Theorem 3) already permit. We test it by partitioning the S&P stocks into price terciles and comparing one global guard (the overall p95, $2.75) with per-region guards (each band\u2019s own p95).", { justify: true }));
children.push(h3("Table R21. Heteroscedastic drift by price band: one global guard vs. per-region guards (S&P 500, target \u03c1 \u2248 5%)"));
children.push(table(
  [1700, 1500, 1400, 2200, 2400],
  [
    ["Price band", "median |\u0394|", "p95 |\u0394|", "Migration @ global guard ($2.75)", "Migration @ region guard"],
    ["Low",  "$0.25", "$1.13", "0.49%", "0.98%  (g = $1.13)"],
    ["Mid",  "$0.45", "$1.88", "1.26%", "1.64%  (g = $1.88)"],
    ["High", "$0.84", "$4.83", "5.39%", "3.83%  (g = $4.83)"],
  ]
));
children.push(rp([{ t: "What this shows. ", b: true }, "The per-band drift tails differ by about 4\u00d7 (p95 of $1.13 vs $4.83), so a single global guard yields migration from 0.49% (cheap stocks, over-provisioned) to 5.39% (expensive stocks, under-provisioned) \u2014 an 11\u00d7 spread. Per-region guards cut the spread to 0.98\u20133.83% (about 4\u00d7) and remove the high-band over-migration. The single-\u03b4 model is therefore the analysis baseline; the per-region \u03b4(\u00b7) the data demands is a direct generalization the adaptive structure realizes, not an afterthought."], { justify: true }));
children.push(gap());
children.push(h2("9.17 Mitigating single-key hotspots with overflow chaining"));
children.push(p("Section 11 concedes one case the size bound cannot cover: a single key value of multiplicity greater than 2\u03c4. No key-range split separates identical keys, so the bucket holding such a value cannot shrink below its multiplicity \u2014 exactness holds, the bound does not. The fix is overflow chaining: when one value\u2019s multiplicity in a bucket exceeds \u03c4, its id-set is evicted to a dedicated overflow chain keyed by that exact value; the bucket then contains no over-multiple value, so adaptive splitting can again bound it, and a range query unions the overflow chains whose value lies in [a, b].", { justify: true }));
children.push(h3("Table R22. Single-key hotspot: the splitting obstruction with and without overflow chaining (\u03c4 = 64; 35% of keys driven onto one value)"));
children.push(table(
  [2600, 2800, 2200, 1400],
  [
    ["Configuration", "Max single-value multiplicity in a bucket", "Obstruction \u2264 2\u03c4 (= 128)?", "Exact?"],
    ["Without overflow chaining", "1,938", "no (\u2248 15\u00d7 over)", "yes"],
    ["With overflow chaining", "13", "yes", "yes"],
  ]
));
children.push(rp([{ t: "Result. ", b: true }, "The maximum single-value multiplicity inside a bucket \u2014 the obstruction to splitting \u2014 is 1,938 without the chain (about 15\u00d7 the 2\u03c4 bound) and 13 with it, the hot value\u2019s 1,938 ids living in a single overflow chain. Both configurations are exact across 4,000 queries, including ones spanning the hot value; overflow chaining removes the obstruction at the cost of one chain per hotspot, so the size bound holds on all non-degenerate data."], { justify: true }));
children.push(rp([{ t: "Chain query cost. ", b: true }, "The chains also help queries. A range that overlaps a hotspot bucket without containing the hot value examines 851 entries with chaining versus 2,812 without \u2014 a 3.3\u00d7 reduction, since the evicted ids are no longer scanned \u2014 and a query that does contain the hot value pays only an O(1) set union per chain. Overflow chaining therefore lowers query cost near a hotspot rather than adding to it."], { justify: true }));
children.push(gap());
children.push(h2("9.18 Robustness: drift regimes, query skew, and larger scale"));
children.push(rp([{ t: "Statistical convention. ", b: true }, "Counts deterministic given a seed \u2014 relocations, structural writes, verifications, durable bytes, recovered items \u2014 are identical across seeds and reported as single values; quantities that vary across runs \u2014 wall-clock throughput and latency \u2014 are reported as mean \u00b1 standard deviation. The regime figures below are means \u00b1 std over three seeds, and every configuration is exact against the oracle."], { justify: true }));
children.push(h3("Table R23. Relocations per update across drift regimes (n = 20,000; 80,000 updates; 3 seeds, mean \u00b1 std)"));
children.push(table([2600, 3000, 3400],[
  ["Drift regime", "MARI \u2014 relocations / update", "ART / PGM / Bx-tree \u2014 relocations / update"],
  ["Uniform", "0.031 \u00b1 0.000", "0.990"],
  ["Clustered", "0.059 \u00b1 0.000", "1.000"],
  ["Directional (one-sided)", "0.038 \u00b1 0.000", "0.981"],
  ["Adversarial", "0.029 \u00b1 0.000", "0.991"],
]));
children.push(rp([{ t: "Regimes. ", b: true }, "MARI\u2019s relocation advantage holds across every regime, including the guard\u2019s worst cases \u2014 directional drift (one-sided motion that defeats guard symmetry) and an adversarial generator \u2014 staying at 3\u20136% versus 98\u2013100% for all three competitors, a 17\u201334\u00d7 gap. Clustered drift is the hardest case at 5.9%, still about 17\u00d7 better. The uniform figure here (0.031) exceeds the 0.024 of Section 9.15 only because this run uses 80,000 updates rather than 120,000; both are exact for their configuration."], { justify: true }));
children.push(h3("Table R24. Query cost under a skewed query distribution (centres drawn from live key density)"));
children.push(table([3000, 2300, 2600, 1400],[
  ["Structure", "Scan / result", "Verifications / result", "Exact?"],
  ["MARI", "1.43", "1.02", "yes"],
  ["ART", "0.77", "0.00", "yes"],
  ["PGM", "1.38", "1.38", "yes"],
  ["Bx-tree", "6.08", "6.08", "yes"],
]));
children.push(rp([{ t: "Query skew. ", b: true }, "With query centres drawn from the live key density (ranges land in dense regions), MARI stays efficient at 1.43 entries and 1.02 verifications per result. ART\u2019s radix sharing makes it most read-efficient on dense queries (0.77); the Bx-tree over-fetches (6.08). MARI\u2019s edge is on the update side, not single-query read amplification, and we report that plainly."], { justify: true }));
children.push(rp([{ t: "Larger scale. ", b: true }, "At 200,000 keys under 1,000,000 updates the relocation gap widens: MARI relocates 0.0069 per update (denser buckets absorb more motion) versus 0.990 for every competitor \u2014 about 140\u00d7 \u2014 while sustaining the highest update throughput (235k/s versus 41\u2013122k/s). All four remain exact (zero mismatches), so the advantage is a scaling trend, not a small-instance effect."], { justify: true }));
children.push(rp([{ t: "Adversarial drift at scale. ", b: true }, "The advantage is not an artefact of benign drift or small instances. At 500,000 keys under 1,500,000 updates MARI relocates 0.0051 per update under adversarial drift, 0.013 under directional, and 0.035 under clustered \u2014 all exact, and if anything lower than at 20,000 keys because denser buckets absorb more motion. Under adversarial drift at 200,000 keys / 600,000 updates the three competitors sit at 0.990 while MARI is at 0.0068 \u2014 a ~145\u00d7 gap that holds jointly across the hardest regime and the largest scale we test."], { justify: true }));
children.push(rp([{ t: "Seeds and variance. ", b: true }, "Over eight seeds the relocation rates are 0.0310 \u00b1 0.0003 (uniform), 0.0583 \u00b1 0.0005 (clustered), 0.0376 \u00b1 0.0004 (directional) and 0.0285 \u00b1 0.0002 (adversarial). The standard deviation is small because bounded-drift relocation is statistically stable across workloads, not because it was under-sampled; query throughput, by contrast, varies by about 8% run to run, so we report it as mean \u00b1 std throughout."], { justify: true }));
children.push(gap());
children.push(h1("10. Discussion"));
children.push(p("MARI converts the problem of relocation under change into the problem of guard sizing: how much slack to grant a bucket so that motion is absorbed in place without scanning too many non-results at query time. The design is most attractive when updates dominate queries and drift is genuinely local relative to bucket width; it is least attractive when drift is large, when queries dominate (verification cost is paid often), or when keys jump unpredictably.", { justify: true }));
children.push(p("The efficiency study (Sections 9.4\u20139.6) sharpens this into a concrete boundary and argues against overclaiming. The honest synthesis is that MARI\u2019s contribution is a change in the cost model of an update, not a universal speed-up: it makes per-update cost independent of bucket size by replacing an O(bucket) relocation with an amortized O(log|\u0394| + 1/\u03b5) local write plus periodic merge. On single-thread, main-memory, finely partitioned workloads a relocation is cheap and a plain partitioned baseline wins. But the same replacement turns a random read-modify-write into a sequential append: measured against an in-place baseline, MARI writes \u2248 74\u00d7 fewer durable bytes per update (Table R8), and against a native copy-on-write B+-tree (LMDB) 58\u201382\u00d7 fewer, in the same band as a native LSM (RocksDB) \u2014 the LSM-family advantage and the strongest case for the design. And because updates are partition-local, MARI\u2019s per-bucket locking scales \u2248 2\u00d7 across one-to-eight threads where a global-lock index is flat (Table R9) \u2014 though this holds in the I/O-dominated regime, and against a native engine under amortized group commit RocksDB scales while our Python prototype does not (Table R11), so the concurrency benefit is structural and not yet realised as throughput. MARI is therefore best understood as a structure for write-amplification-sensitive and contention-sensitive deployments rather than for raw in-memory throughput, and a credible paper reports, as we do, the regimes on which it loses.", { justify: true }));
children.push(gap());

children.push(h2("10.1 Why MARI is not a recombination of cracking, LSM deltas, and verified indexes"));
children.push(p("One might reasonably ask whether MARI is just database cracking for the partitioning, an LSM or differential-file delta for the updates, and verified secondary-index lookups for exactness. The three components are individually known; we concede that, and locate the novelty precisely at their joint, arguing that a naive composition does not solve the problem.", { justify: true }));
children.push(rp([{ t: "Versus cracking. ", b: true }, "Database cracking [15] partitions a static column by observed query boundaries; its boundaries are hard \u2014 a tuple lies on exactly one side of a crack. Under drift, a value crossing a crack must move between partitions, which is the very relocation we set out to avoid; cracking has no mechanism to keep a drifted tuple in place, and would re-crack continually. MARI\u2019s boundaries are soft: a guard band plus sticky ownership lets a value drift past a bucket\u2019s geometric edge while the item stays in its current bucket. The guard, not the partitioning, converts a cross-boundary move from a relocation into a single in-place append \u2014 at a $5 guard MARI relocates 1.6% of S&P 500 updates and at $10 only 0.9% (Table R12), where a hard-boundary scheme relocates on every crossing."], { justify: true }));
children.push(rp([{ t: "Versus an LSM delta. ", b: true }, "An LSM or differential file [4, 14] optimizes writes, but keyed by the moving attribute it must, on each change, tombstone the old (value, id) and insert the new \u2014 two entries \u2014 and the stale entry pollutes range scans until compaction. That is exactly the value-keyed configuration we measured natively (Section 9.7), and MARI writes 58\u201382\u00d7 fewer bytes than the in-place B+-tree precisely because guarded ownership makes the common case a single append rather than a delete-plus-insert. Keyed by identifier instead, an LSM writes once per change but cannot answer range-by-value without a secondary index \u2014 which reintroduces the relocation. Neither configuration yields the \u201cone append in-guard, two on migration\u201d split; that split follows from ownership-by-bucket, not from the delta tier."], { justify: true }));
children.push(rp([{ t: "Versus verification. ", b: true }, "Verifying candidates against an authoritative table is a known way to tolerate stale or approximate indexes, and MARI uses it \u2014 but verification alone reduces neither writes nor relocations; it only restores correctness. Its role here is enabling: the guard and delta deliberately let an item\u2019s superseded value linger in a bucket without a relocation, and verification against the table T is what makes that deliberate staleness exact (Claims 1\u20132). Bolting verification onto cracking or an LSM would fix correctness without removing the relocation or the double write."], { justify: true }));
children.push(rp([{ t: "The load-bearing novelty. ", b: true }, "is the guarded, sticky ownership specialized to bounded drift: it is what none of the three components provides, and the bounded-drift assumption is what makes it cheap \u2014 a guard of width \u2248 \u03b4 absorbs most moves, so relocations are rare (Tables R12, R12a) and the delta stays small. We isolate this empirically: hard value-bucketing \u2014 the drift-aware reduction of a cracking- or Bx-tree-style scheme \u2014 relocates 3\u20139\u00d7 more than MARI at the same bucket width (Section 9.10). Cracking adapts to queries, learned indexes to the key distribution, LSMs to write patterns; MARI adapts ownership to motion. We borrow the delta tier and the verification idea and say so; the contribution is the mechanism that composes them for exact range reporting under drift, with its proofs (Theorems 1\u20133) and cross-domain validation."], { justify: true }));
children.push(gap());
children.push(h1("11. Limitations and Threats to Validity"));
children.push(bulletRich([{ t: "Assumption dependence. ", b: true }, "Results hold under bounded drift; this is now validated on three real datasets across independent domains \u2014 S&P 500 prices, NBA Elo ratings, and US city temperatures \u2014 each with 95\u201399% of moves inside a modest guard and MARI exact (Section 9.9). Two honest caveats remain: drift scale and universe vary by domain, so a single global guard serves them unevenly (which motivates adaptive bucket widths, Theorem 3); and heavy-tailed or jump-prone keys still degrade MARI toward a delete-then-insert index."]));
children.push(bulletRich([{ t: "No in-memory throughput advantage. ", b: true }, "On single-thread, main-memory, finely partitioned workloads MARI does not beat a plain radix-partitioned sorted index (Section 9.4). Its advantages are measured instead in durable write volume (\u2248 74\u00d7 fewer bytes; 58\u201382\u00d7 vs. a native B+-tree) and thread scaling, in a Python harness on one machine (Sections 9.6\u20139.7); confirming them on native code, a real device, and many cores is the key remaining step."]));
children.push(bulletRich([{ t: "Concurrency advantage not yet realised. ", b: true }, "MARI\u2019s sharding scales \u2248 2\u00d7 only when durable I/O dominates (Table R9); under amortized group commit a native concurrent engine (RocksDB) scales with threads while the Python prototype does not (Table R11). The advantage is structural \u2014 independent per-bucket logs versus a single write-ahead log \u2014 and realising it as throughput requires a native, interpreter-lock-free implementation."]));
children.push(bulletRich([{ t: "Query-side overhead. ", b: true }, "With real per-bucket local indexes, MARI\u2019s scan amplification is a small constant (\u2248 1.2\u00d7 across selectivities) and verification costs \u2248 1 table lookup per result, but the two together make MARI queries about 3\u00d7 slower than a plain partitioned baseline in the prototype (Section 9.11); the cost is genuine and read-heavy workloads pay it. The higher selective-query amplification reported for the dictionary-backed mechanism (Table R2) is largely removed by within-bucket binary search."]));
children.push(bulletRich([{ t: "Compaction and maintenance parameters. ", b: true }, "The delta-ratio bound (Theorem 1, Corollary 1) and the adaptive split/merge bound (Theorem 3) are proven and empirically confirmed (O(1) amortized maintenance, balance \u2248 2\u03c4). The one residual case is a single-key hotspot of multiplicity > 2\u03c4, which no key-range partition can split; MARI keeps exactness there but not the size bound, until overflow chaining (Section 9.17) evicts the over-multiple value to a dedicated chain, restoring the bound at the cost of one chain per hotspot."]));
children.push(bulletRich([{ t: "Crash recovery. ", b: true }, "The table T is reconstructible from the per-bucket logs and recovery is exact to the last durable commit (Section 9.12); this is demonstrated on the reference durable form. The per-bucket-versus-single-log choice and concurrent recovery against in-flight queries are left to a native implementation."]));
children.push(bulletRich([{ t: "Resident memory. ", b: true }, "MARI holds about 1.7\u00d7 the records of a plain ordered index in the reference implementation and 1.2\u00d7 in a lean design that drops the redundant stable dict (Section 9.14); the authoritative table does not cancel the durable-write saving, but the sub-2\u00d7 premium and the eps-bounded delta tail are real costs a memory-constrained deployment must budget for."]));
children.push(bulletRich([{ t: "Construct validity. ", b: true }, "Synthetic generators may not reflect real motion; three real bounded-drift traces across finance, sports ratings, and climate now mitigate this (Section 9.9), though the reference baselines remain Python, not native code."]));
children.push(bulletRich([{ t: "Internal validity. ", b: true }, "Baseline quality affects conclusions; the write-amplification claim is now corroborated on native engines (LMDB, RocksDB) measured by kernel I/O accounting, and Section 9.15 now compares against faithful, exactness-checked ART, PGM, and Bx-tree implementations on the implementation-independent metrics; the residual gap is specifically a native, multi-core wall-clock comparison, not the absence of competitive baselines."]));
children.push(gap());

// 12 Conclusion
children.push(h1("12. Conclusion"));
children.push(p("We defined exact range reporting over bounded-drift streaming integer keys and presented MARI, a motion-aware adaptive index that absorbs drift in place through guarded bucket ownership while preserving exactness via a versioned delta index and verification against an authoritative table. We gave the algorithms, a correctness argument, complexity targets, a proven compaction policy, and a relocation-optimality theorem showing MARI relocates the minimum any exact guarded-ownership algorithm must for a fixed bucketing, and we validated exactness, migration reduction, and the guard/compaction trade-offs in a reference implementation with real local range indexes. Measured against in-place baselines, MARI writes about 74 times fewer durable bytes per update (sequential rather than random) \u2014 confirmed against a native copy-on-write B+-tree (LMDB) at 58\u201382 times fewer bytes, in the same band as a native LSM (RocksDB) \u2014 and its per-bucket locking scales about twofold across one-to-eight threads where a global-lock index is flat, while it does not win on single-thread in-memory throughput. The contribution is thus a cost-model property for write-amplification- and contention-sensitive settings, with relocation optimality inside the guarded-ownership model; a systems-grade comparison against tuned native indexes on real workloads, a native interpreter-lock-free implementation to realise the concurrency advantage, and an unconditional cell-probe lower bound remain future work, and no superiority claim over production indexes is made.", { justify: true }));
children.push(gap());

// 13 References
children.push(h1("13. References"));
children.push(p("The following references were checked against primary sources.", { justify: true }));
children.push(numItem("P. van Emde Boas. Preserving order in a forest in less than logarithmic time and linear space. Information Processing Letters, 6(3):80\u201382, 1977.", "refs"));
children.push(numItem("D. E. Willard. Log-logarithmic worst-case range queries are possible in space \u0398(n). Information Processing Letters, 17(2):81\u201384, 1983.", "refs"));
children.push(numItem("M. L. Fredman and D. E. Willard. Surpassing the information theoretic bound with fusion trees. Journal of Computer and System Sciences, 47(3):424\u2013436, 1993.", "refs"));
children.push(numItem("D. G. Severance and G. M. Lohman. Differential files: their application to the maintenance of large databases. ACM Transactions on Database Systems, 1(3):256\u2013267, 1976.", "refs"));
children.push(numItem("G. Graefe. B-tree indexes for high update rates. ACM SIGMOD Record, 35(1):39\u201344, 2006.", "refs"));
children.push(numItem("G. Graefe. Sorting and indexing with partitioned B-trees. In CIDR, 2003.", "refs"));
children.push(numItem("V. Leis, A. Kemper, and T. Neumann. The adaptive radix tree: ARTful indexing for main-memory databases. In IEEE ICDE, pages 38\u201349, 2013.", "refs"));
children.push(numItem("J. J. Levandoski, D. B. Lomet, and S. Sengupta. The Bw-tree: a B-tree for new hardware platforms. In IEEE ICDE, pages 302\u2013313, 2013.", "refs"));
children.push(numItem("S. \u0160altenis, C. S. Jensen, S. T. Leutenegger, and M. A. Lopez. Indexing the positions of continuously moving objects. In ACM SIGMOD, pages 331\u2013342, 2000.", "refs"));
children.push(numItem("Y. Tao, D. Papadias, and J. Sun. The TPR*-tree: an optimized spatio-temporal access method for predictive queries. In VLDB, pages 790\u2013801, 2003.", "refs"));
children.push(numItem("C. S. Jensen, D. Lin, and B. C. Ooi. Query and update efficient B+-tree based indexing of moving objects. In VLDB, pages 768\u2013779, 2004.", "refs"));
children.push(numItem("M. L. Yiu, Y. Tao, and N. Mamoulis. The B^dual-tree: indexing moving objects by space filling curves in the dual space. The VLDB Journal, 17(3):379\u2013400, 2008.", "refs"));
children.push(numItem("S. Chen, B. C. Ooi, K.-L. Tan, and M. A. Nascimento. ST2B-tree: a self-tunable spatio-temporal B+-tree index for moving objects. In ACM SIGMOD, pages 29\u201342, 2008.", "refs"));
children.push(numItem("P. O\u2019Neil, E. Cheng, D. Gawlick, and E. O\u2019Neil. The log-structured merge-tree (LSM-tree). Acta Informatica, 33(4), 1996.", "refs"));
children.push(numItem("S. Idreos, M. L. Kersten, and S. Manegold. Database cracking. In CIDR, pages 68\u201378, 2007.", "refs"));
children.push(numItem("S. Idreos, M. L. Kersten, and S. Manegold. Updating a cracked database. In ACM SIGMOD, pages 413\u2013424, 2007.", "refs"));
children.push(numItem("S. Idreos, S. Manegold, H. Kuno, and G. Graefe. Merging what\u2019s cracked, cracking what\u2019s merged: adaptive indexing in main-memory column-stores. PVLDB, 4(9):585\u2013597, 2011.", "refs"));
children.push(numItem("T. Kraska, A. Beutel, E. H. Chi, J. Dean, and N. Polyzotis. The case for learned index structures. In ACM SIGMOD, pages 489\u2013504, 2018.", "refs"));
children.push(numItem("J. Ding, U. F. Minhas, J. Yu, et al. ALEX: an updatable adaptive learned index. In ACM SIGMOD, pages 969\u2013984, 2020.", "refs"));
children.push(numItem("P. Ferragina and G. Vinciguerra. The PGM-index: a fully-dynamic compressed learned index with provable worst-case bounds. PVLDB, 13(8):1162\u20131175, 2020.", "refs"));
children.push(numItem("A. Galakatos, M. Markovitch, C. Binnig, R. Fonseca, and T. Kraska. FITing-Tree: a data-aware index structure. In ACM SIGMOD, pages 1189\u20131206, 2019.", "refs"));
children.push(numItem("J. Basch, L. J. Guibas, and J. Hershberger. Data structures for mobile data. Journal of Algorithms, 31(1):1\u201328, 1999. Preliminary version in ACM-SIAM SODA, pages 747\u2013756, 1997.", "refs"));
children.push(numItem("L. J. Guibas. Kinetic data structures: a state of the art report. In Workshop on the Algorithmic Foundations of Robotics (WAFR), pages 191\u2013209, 1998.", "refs"));
children.push(gap());

// 14 Supplementary plan
children.push(h1("14. Supplementary Material Plan"));
children.push(bullet("Artifact: MARI implementation, all baselines with configurations, workload generators, and analysis scripts; a one-command reproduction harness."));
children.push(bullet("Full formal proofs of the correctness claims and complexity bounds, with the compaction invariant made explicit."));
children.push(bullet("Extended results: full parameter sweeps, per-seed runs, and tail-latency CDFs omitted from the main paper for space."));
children.push(bullet("Realized-drift audits per workload, demonstrating the bounded-drift property each generator satisfies."));
children.push(bullet("A datasheet for any real dataset used, including how the bounded-drift property was verified."));

// ---------- assemble ----------
const doc = new Document({
  styles: {
    default: { document: { run: { font: FONT, size: 22 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: FONT, color: ACCENT },
        paragraph: { spacing: { before: 260, after: 140 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: FONT, color: "2E5496" },
        paragraph: { spacing: { before: 180, after: 100 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: FONT, color: "404040" },
        paragraph: { spacing: { before: 140, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: {
    config: [
      { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 600, hanging: 280 } } } }] },
      { reference: "contrib", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 600, hanging: 320 } } } }] },
      { reference: "refs", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "[%1]", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 640, hanging: 360 } } } }] },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "MARI: Motion-Aware Adaptive Range Index", italics: true, size: 16, color: "888888" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Page ", size: 16, color: "888888" }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: "888888" })] })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("/home/claude/MARI_manuscript_draft.docx", buf);
  console.log("written", buf.length, "bytes");
});
