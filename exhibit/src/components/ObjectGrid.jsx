import { useState, useMemo, Fragment } from 'react';
import { useLang } from '../i18n/useLang.js';
import { ui } from '../i18n/ui.js';

// LANG_NAMES now comes from the i18n dictionary (see t.langNames below)

// ── Colour helpers (module-level so they're reusable) ──────────────────────
function satFromHex(hex) {
  if (!hex || hex.length < 7) return 0;
  const r = parseInt(hex.slice(1, 3), 16) / 255;
  const g = parseInt(hex.slice(3, 5), 16) / 255;
  const b = parseInt(hex.slice(5, 7), 16) / 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  const l = (max + min) / 2;
  return l === 0 || l === 1 ? 0 : (max - min) / (1 - Math.abs(2 * l - 1));
}

function colorGroupKey(card) {
  const all = card.color_palette?.length
    ? card.color_palette
    : card.color_hex ? [{ hex: card.color_hex, hue: card.color_hue ?? 0 }] : [];
  const withSat = all.map(e => ({ ...e, _s: satFromHex(e.hex) }));
  const best = [...withSat].sort((a, b) => b._s - a._s)[0];
  if (!best || best._s < 0.08) return 'gray';
  if (best._s < 0.22) return (best.hue >= 10 && best.hue <= 60) ? 'sepia' : 'gray';
  const h = best.hue;
  if (h < 20 || h >= 340) return 'red';
  if (h < 50)  return 'orange';
  if (h < 75)  return 'yellow';
  if (h < 165) return 'green';
  if (h < 200) return 'cyan';
  if (h < 260) return 'blue';
  return 'purple';
}

const GROUP_ORDER = ['red', 'orange', 'yellow', 'green', 'cyan', 'blue', 'purple', 'sepia', 'gray'];
const GROUP_META = {
  red:    { label: 'Red',           swatch: '#c0392b' },
  orange: { label: 'Orange',        swatch: '#e67e22' },
  yellow: { label: 'Yellow',        swatch: '#c9a800' },
  green:  { label: 'Green',         swatch: '#27ae60' },
  cyan:   { label: 'Cyan',          swatch: '#17a589' },
  blue:   { label: 'Blue',          swatch: '#2471a3' },
  purple: { label: 'Purple',        swatch: '#8e44ad' },
  sepia:  { label: 'Sepia / Brown', swatch: '#c9a96e' },
  gray:   { label: 'Grayscale',     swatch: '#7f8c8d' },
};
// ────────────────────────────────────────────────────────────────────────────

function primaryLang(code) {
  if (!code) return null;
  return code.split(/[;,\s]/)[0].trim().toLowerCase();
}

export default function ObjectGrid({ postcards, base }) {
  const lang = useLang();
  const t = ui[lang] ?? ui.en;
  // ---- derived filter options (memoized once) ----
  const allSubjects = useMemo(() => {
    const s = new Set();
    postcards.forEach(p => p.subjects?.forEach(t => s.add(t)));
    return [...s].sort();
  }, [postcards]);

  const allLangs = useMemo(() => {
    const m = new Map();
    postcards.forEach(p => {
      const l = primaryLang(p.language);
      if (l) m.set(l, t.langNames[l] ?? l);
    });
    return [...m.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  }, [postcards, lang]);

  // ---- filter / sort state ----
  const [activeSubject, setActiveSubject] = useState(null);
  const [activeLangs,   setActiveLangs]   = useState(new Set());
  const [sortMode,      setSortMode]      = useState('richness-desc');
  const [cellSize,      setCellSize]      = useState(155); // px — drives grid column width
  const [paletteMode,   setPaletteMode]   = useState(false);

  // ---- filtered + sorted results ----
  const visible = useMemo(() => {
    let res = postcards;

    if (activeSubject)
      res = res.filter(p => p.subjects?.includes(activeSubject));

    if (activeLangs.size > 0)
      res = res.filter(p => activeLangs.has(primaryLang(p.language)));

    const sorted = [...res];
    if (sortMode === 'richness-asc')
      sorted.sort((a, b) => (a.color_palette?.length ?? 0) - (b.color_palette?.length ?? 0));
    else if (sortMode === 'richness-desc')
      sorted.sort((a, b) => (b.color_palette?.length ?? 0) - (a.color_palette?.length ?? 0));
    else if (sortMode === 'date')
      sorted.sort((a, b) => (a.date ?? '9999').localeCompare(b.date ?? '9999'));
    else if (sortMode === 'title')
      sorted.sort((a, b) => a.title.localeCompare(b.title));

    return sorted;
  }, [postcards, activeSubject, activeLangs, sortMode]);

  // ---- colour-group buckets (only computed in 'group' mode) ----
  const visibleGroups = useMemo(() => {
    if (sortMode !== 'group') return null;
    const byGroup = new Map(GROUP_ORDER.map(k => [k, []]));
    visible.forEach(card => byGroup.get(colorGroupKey(card))?.push(card));
    // within each group: most saturated first
    byGroup.forEach(cards => cards.sort((a, b) => {
      const sA = Math.max(0, ...(a.color_palette ?? []).map(e => satFromHex(e.hex)));
      const sB = Math.max(0, ...(b.color_palette ?? []).map(e => satFromHex(e.hex)));
      return sB - sA;
    }));
    return GROUP_ORDER
      .filter(k => byGroup.get(k).length > 0)
      .map(k => ({ key: k, ...GROUP_META[k], cards: byGroup.get(k) }))
      .sort((a, b) => b.cards.length - a.cards.length);
  }, [visible, sortMode]);

  function toggleLang(code) {
    setActiveLangs(prev => {
      const next = new Set(prev);
      next.has(code) ? next.delete(code) : next.add(code);
      return next;
    });
  }

  // ---- styles (all inline to avoid Astro scoping issues in islands) ----
  const S = styles;

  function renderCard(card) {
    const backThumb = card.image_back ? `thumb_${card.image_back}` : null;
    return (
      <a
        key={card.objectid}
        href={`${base}detail/${card.objectid}`}
        className={`grid-flip-cell${paletteMode ? ' palette-on' : ''}`}
        style={S.cell}
        title={card.title}
      >
        <div className="grid-flip-inner">
          {/* Front */}
          <div className="grid-flip-face">
            {card.image_thumb
              ? <img src={`${base}images/${card.image_thumb}`} alt={card.title} loading="lazy" style={S.thumb} />
              : <div style={S.noImg}>?</div>
            }
          </div>
          {/* Back */}
          <div className="grid-flip-face grid-flip-back-face">
            {backThumb
              ? <img src={`${base}images/${backThumb}`} alt={t.cardBack(card.title)} loading="lazy" style={S.thumb} />
              : <div style={S.noImg}>∅</div>
            }
          </div>
        </div>
        {/* Palette overlay */}
        {card.color_palette?.length > 0 && (() => {
          const pal = card.color_palette;
          const rows = pal.length >= 3 ? '1fr 1fr' : '1fr';
          return (
            <div className="palette-overlay" style={{ gridTemplateRows: rows }}>
              {pal.map((c, i) => (
                <div
                  key={i}
                  className="palette-tile"
                  style={{
                    background: c.hex,
                    gridColumn: pal.length === 1 || (pal.length === 3 && i === 2) ? 'span 2' : undefined,
                  }}
                />
              ))}
            </div>
          );
        })()}
        {/* Bottom colour bar — hidden in palette mode */}
        {!paletteMode && (
          card.color_palette?.length > 0
            ? (
              <div style={S.colorBar}>
                {card.color_palette.map((c, i) => (
                  <div key={i} style={{ background: c.hex, flex: c.pct }} />
                ))}
              </div>
            ) : card.color_hex ? (
              <div style={{ ...S.colorBar, background: card.color_hex }} />
            ) : null
        )}
      </a>
    );
  }

  return (
    <div>
      {/* ---- Controls bar ---- */}
      <div style={S.controls}>

        {/* Sort */}
        <div style={S.group}>
          <span style={S.label}>{t.sort}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div style={S.segmented}>
              {[
                ['richness-desc', t.sortRichnessDesc],
                ['richness-asc',  t.sortRichnessAsc],
                ['group',         t.sortGroup],
              ].map(([v, label]) => (
                <button
                  key={v}
                  onClick={() => setSortMode(v)}
                  style={{ ...S.segBtn, ...(sortMode === v ? S.segBtnOn : {}) }}
                >{label}</button>
              ))}
            </div>
            {/* Palette toggle — small pill inline with sort */}
            <button
              onClick={() => setPaletteMode(m => !m)}
              title={paletteMode ? 'Show images' : 'Show colour palettes'}
              style={{ ...S.pill, ...(paletteMode ? S.pillOn : {}), fontSize: '0.73rem' }}
            >🎨 Discover the color</button>
          </div>
        </div>

        {/* Subject pills — temporarily hidden until subjects are better normalised
        <div style={S.group}>
          <span style={S.label}>Tema</span>
          <div style={S.pills}>
            <button
              onClick={() => setActiveSubject(null)}
              style={{ ...S.pill, ...(activeSubject === null ? S.pillOn : {}) }}
            >Todos</button>
            {allSubjects.map(s => (
              <button
                key={s}
                onClick={() => setActiveSubject(activeSubject === s ? null : s)}
                style={{ ...S.pill, ...(activeSubject === s ? S.pillOn : {}) }}
              >{s}</button>
            ))}
          </div>
        </div>
        */}

        {/* Language pills */}
        <div style={S.group}>
          <span style={S.label}>{t.language}</span>
          <div style={S.pills}>
            {allLangs.map(([code, label]) => (
              <button
                key={code}
                onClick={() => toggleLang(code)}
                style={{ ...S.pill, ...(activeLangs.has(code) ? S.pillOn : {}) }}
              >{label}</button>
            ))}
          </div>
        </div>

        {/* Grid size */}
        <div style={S.group}>
          <span style={S.label}>{t.size}</span>
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <span style={{ ...S.label, minWidth: 'unset', fontSize: '1rem' }}>▪</span>
            <input
              type="range" min={5} max={250} step={5} value={cellSize}
              onChange={e => setCellSize(+e.target.value)}
              style={{ ...S.slider, width: '140px' }}
            />
            <span style={{ ...S.label, minWidth: 'unset', fontSize: '2rem' }}>▪</span>
          </div>
        </div>

        <span style={{ ...S.label, marginLeft: 'auto', alignSelf: 'center' }}>
          {t.postcards(visible.length)}
        </span>
      </div>

      {/* ---- Thumbnail grid ---- */}
      <style>{`
        .grid-flip-cell { perspective: 900px; }
        .grid-flip-inner {
          width: 100%; height: 100%;
          position: relative;
          transform-style: preserve-3d;
          transition: transform 0.55s cubic-bezier(0.22, 1, 0.36, 1);
          will-change: transform;
        }
        .grid-flip-cell:not(.palette-on):hover .grid-flip-inner { transform: rotateY(180deg); }
        .grid-flip-face {
          position: absolute; inset: 0;
          backface-visibility: hidden;
          -webkit-backface-visibility: hidden;
        }
        .grid-flip-back-face { transform: rotateY(180deg); }
        .palette-overlay {
          position: absolute; inset: 0;
          display: grid;
          grid-template-columns: 1fr 1fr;
          overflow: hidden;
          opacity: 0;
          transition: opacity 0.25s;
        }
        .palette-on .palette-overlay { opacity: 1; }
        .palette-tile {}
      `}</style>
      <div style={{ ...S.grid, gridTemplateColumns: `repeat(auto-fill, minmax(${cellSize}px, 1fr))`, gap: `${Math.max(1, Math.round(cellSize / 60))}px` }}>
        {sortMode === 'group' && visibleGroups
          ? visibleGroups.map(({ key, label, swatch, cards }) => (
              <Fragment key={key}>
                <div style={{ gridColumn: '1 / -1', ...S.groupHeader }}>
                  <span style={{ ...S.groupSwatch, background: swatch }} />
                  <span style={S.groupLabel}>{label}</span>
                  <span style={S.groupCount}>{cards.length}</span>
                </div>
                {cards.map(renderCard)}
              </Fragment>
            ))
          : visible.map(renderCard)
        }
      </div>
    </div>
  );
}

const styles = {
  controls: {
    display: 'flex',
    flexDirection: 'column',
    gap: '0.85rem',
    padding: '1rem 1.25rem',
    background: '#1f1c19',
    border: '1px solid #3a342d',
    borderRadius: '6px',
    marginBottom: '1.25rem',
  },
  group: { display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem' },
  label: {
    fontSize: '0.7rem', color: '#9a8c7e',
    textTransform: 'uppercase', letterSpacing: '0.09em',
    minWidth: '68px', flexShrink: 0,
  },
  segmented: {
    display: 'flex',
    border: '1px solid #3a342d',
    borderRadius: '4px',
    overflow: 'hidden',
  },
  segBtn: {
    padding: '0.28rem 0.7rem',
    fontSize: '0.78rem',
    background: 'transparent',
    border: 'none',
    borderRight: '1px solid #3a342d',
    color: '#9a8c7e',
    cursor: 'pointer',
  },
  segBtnOn: { background: '#c9964a', color: '#141210', fontWeight: 600 },
  pills: { display: 'flex', flexWrap: 'wrap', gap: '0.3rem' },
  pill: {
    padding: '0.18rem 0.55rem',
    fontSize: '0.73rem',
    background: 'transparent',
    border: '1px solid #3a342d',
    borderRadius: '999px',
    color: '#9a8c7e',
    cursor: 'pointer',
  },
  pillOn: { background: '#c9964a', borderColor: '#c9964a', color: '#141210' },
  slider: {
    WebkitAppearance: 'none',
    appearance: 'none',
    width: '110px', height: '3px',
    background: '#3a342d', borderRadius: '2px',
    outline: 'none', cursor: 'pointer',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(155px, 1fr))',
    gap: '3px',
  },
  cell: {
    display: 'block',
    aspectRatio: '4/3',
    overflow: 'hidden',
    position: 'relative',
    background: '#1f1c19',
    textDecoration: 'none',
  },
  thumb: {
    width: '100%', height: '100%',
    objectFit: 'cover',
    transition: 'transform 0.3s',
    display: 'block',
  },
  noImg: {
    width: '100%', height: '100%',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: '#3a342d', fontSize: '1.5rem',
  },
  colorBar: {
    position: 'absolute',
    bottom: 0, left: 0, right: 0,
    height: '5px',
    display: 'flex',
  },
  groupHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.6rem',
    padding: '0.6rem 0.25rem 0.3rem',
    borderBottom: '1px solid #3a342d',
    marginBottom: '2px',
  },
  groupSwatch: {
    width: '10px', height: '10px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  groupLabel: {
    fontSize: '0.72rem',
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    color: '#c9b8a4',
    fontWeight: 600,
  },
  groupCount: {
    fontSize: '0.68rem',
    color: '#6a5f54',
    marginLeft: '0.25rem',
  },
};
