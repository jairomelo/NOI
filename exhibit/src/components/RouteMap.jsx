import { useState, useEffect, useRef, useMemo } from 'react';

// ---- helpers ----

const STREET_RE = /^(via |piazza |calle |rue |avenue |straße |str\. |blvd |boulevard |place |campo |ponte |dorsoduro |palazzo |corte |fondamenta )/i;

function extractCity(location) {
  if (!location) return null;
  const parts = location.split(',').map(s => s.trim()).filter(Boolean);
  if (parts.length === 0) return null;
  if (parts.length <= 2) return parts[0];
  // 3+ parts: first part may be a street — scan for a city-like segment
  if (STREET_RE.test(parts[0])) {
    for (let i = 1; i < parts.length - 1; i++) {
      const p = parts[i];
      if (!/^\d/.test(p) && !STREET_RE.test(p)) {
        // strip postal code prefix and state abbreviation: "50122 Firenze FI" → "Firenze"
        return p.replace(/^\d+\s*/, '').replace(/\s+[A-Z]{2}\s*$/, '').trim();
      }
    }
  }
  return parts[0];
}

function groupByCity(postcards) {
  const groups = {};
  for (const card of postcards) {
    const city = extractCity(card.location) ?? 'Otros';
    if (!groups[city]) groups[city] = [];
    groups[city].push(card);
  }
  // Sort cities by card count descending
  return Object.fromEntries(
    Object.entries(groups).sort((a, b) => b[1].length - a[1].length)
  );
}

// ---- component ----

export default function RouteMap({ postcards, base }) {
  const mapRef           = useRef(null);
  const mapInstanceRef   = useRef(null);   // { map, L }
  const markersLayerRef  = useRef(null);

  const cityGroups = useMemo(() => groupByCity(postcards), [postcards]);
  const cityNames  = useMemo(() => Object.keys(cityGroups), [cityGroups]);

  const [selectedCity, setSelectedCity] = useState(cityNames[0] ?? null);
  const [selectedCard, setSelectedCard] = useState(null);
  const [routeIndex,   setRouteIndex]   = useState(0);
  const [wikiSummary,  setWikiSummary]  = useState(null);
  const [wikiLoading,  setWikiLoading]  = useState(false);

  const cityCards = useMemo(
    () => (selectedCity ? cityGroups[selectedCity] ?? [] : []),
    [selectedCity, cityGroups],
  );

  // ---- init Leaflet (once, client-side only) ----
  useEffect(() => {
    if (typeof window === 'undefined' || mapInstanceRef.current) return;

    import('leaflet').then(L => {
      // Fix Leaflet's default icon path handling in bundled environments
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
      });

      const map = L.map(mapRef.current, { center: [46, 10], zoom: 4 });

      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        maxZoom: 18,
      }).addTo(map);

      markersLayerRef.current = L.layerGroup().addTo(map);
      mapInstanceRef.current  = { map, L };
    });

    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.map.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // ---- update markers when city changes ----
  useEffect(() => {
    if (!mapInstanceRef.current || !cityCards.length) return;
    const { map, L } = mapInstanceRef.current;
    markersLayerRef.current.clearLayers();

    const bounds = [];

    cityCards.forEach((card, i) => {
      if (!card.latitude || !card.longitude) return;
      bounds.push([card.latitude, card.longitude]);

      const thumbUrl = card.image_thumb ? `${base}images/${card.image_thumb}` : null;

      const icon = thumbUrl
        ? L.divIcon({
            html: `<div style="width:48px;height:48px;border-radius:4px;overflow:hidden;border:2px solid #c9964a;box-shadow:0 2px 10px rgba(0,0,0,.6);background:#1f1c19">
                     <img src="${thumbUrl}" style="width:100%;height:100%;object-fit:cover" />
                   </div>`,
            className: '',
            iconSize:   [48, 48],
            iconAnchor: [24, 24],
          })
        : L.divIcon({
            html: `<div style="width:28px;height:28px;border-radius:50%;background:#c9964a;display:flex;align-items:center;justify-content:center;color:#141210;font-weight:700;font-size:11px">${i + 1}</div>`,
            className: '',
            iconSize:   [28, 28],
            iconAnchor: [14, 14],
          });

      const marker = L.marker([card.latitude, card.longitude], { icon });
      marker.on('click', () => {
        setSelectedCard(card);
        setRouteIndex(i);
      });
      markersLayerRef.current.addLayer(marker);
    });

    if (bounds.length > 0) {
      try { map.fitBounds(bounds, { padding: [50, 50] }); }
      catch { map.setView(bounds[0], 13); }
    }

    // auto-select first card
    setSelectedCard(cityCards[0] ?? null);
    setRouteIndex(0);
  }, [selectedCity, cityCards, base]);

  // ---- Wikipedia lookup when card changes ----
  useEffect(() => {
    if (!selectedCard?.location) { setWikiSummary(null); return; }

    const searchTerm = extractCity(selectedCard.location) ?? selectedCard.location.split(',')[0].trim();
    if (!searchTerm) { setWikiSummary(null); return; }

    setWikiLoading(true);
    setWikiSummary(null);

    fetch(`https://en.wikipedia.org/api/rest_v1/page/summary/${encodeURIComponent(searchTerm)}`)
      .then(r => (r.ok ? r.json() : null))
      .then(data => {
        if (data?.extract) {
          setWikiSummary({
            title:   data.title,
            extract: data.extract,
            url:     data.content_urls?.desktop?.page,
          });
        } else {
          setWikiSummary(null);
        }
      })
      .catch(() => setWikiSummary(null))
      .finally(() => setWikiLoading(false));
  }, [selectedCard?.objectid]);

  // ---- navigate route ----
  function goTo(i) {
    const card = cityCards[i];
    if (!card) return;
    setSelectedCard(card);
    setRouteIndex(i);
    if (mapInstanceRef.current && card.latitude && card.longitude) {
      mapInstanceRef.current.map.setView([card.latitude, card.longitude], 14, { animate: true });
    }
  }

  const S = styles;

  return (
    <div style={S.wrap}>

      {/* City selector */}
      <div style={S.cityBar}>
        <label style={S.label}>Lugar:</label>
        <select
          value={selectedCity ?? ''}
          onChange={e => { setSelectedCity(e.target.value); setSelectedCard(null); }}
          style={S.select}
        >
          {cityNames.map(c => (
            <option key={c} value={c}>{c}  ({cityGroups[c].length})</option>
          ))}
        </select>
        <span style={S.muted}>{cityCards.length} postales</span>
      </div>

      {/* Map + detail panel (two columns on wide screens via CSS class) */}
      <div className="route-map-layout" style={S.mapLayout}>

        {/* Leaflet target */}
        <div ref={mapRef} style={S.mapBox} />

        {/* Side panel */}
        {selectedCard && (
          <div style={S.panel}>

            {/* Route prev/next */}
            <div style={S.routeNav}>
              <button
                onClick={() => goTo(routeIndex - 1)}
                disabled={routeIndex === 0}
                style={{ ...S.navBtn, ...(routeIndex === 0 ? S.navBtnOff : {}) }}
              >←</button>
              <span style={S.muted}>{routeIndex + 1} / {cityCards.length}</span>
              <button
                onClick={() => goTo(routeIndex + 1)}
                disabled={routeIndex >= cityCards.length - 1}
                style={{ ...S.navBtn, ...(routeIndex >= cityCards.length - 1 ? S.navBtnOff : {}) }}
              >→</button>
            </div>

            {/* Postcard image */}
            {selectedCard.image_front && (
              <img
                src={`${base}images/${selectedCard.image_front}`}
                alt={selectedCard.title}
                style={S.panelImg}
              />
            )}

            {/* Historical info */}
            <div style={S.panelBody}>
              <h2 style={S.panelTitle}>{selectedCard.title}</h2>
              {selectedCard.date && <p style={S.panelDate}>{selectedCard.date}</p>}
              {selectedCard.description && (
                <p style={S.panelDesc}>{selectedCard.description}</p>
              )}
              <a href={`${base}detail/${selectedCard.objectid}`} style={S.panelLink}>
                Ver objeto completo →
              </a>
            </div>

            {/* Wikipedia: current context */}
            <div style={S.wikiBlock}>
              <p style={S.wikiHead}>Contexto actual — Wikipedia</p>
              {wikiLoading && <p style={S.muted}>Buscando…</p>}
              {wikiSummary && (
                <>
                  <p style={S.wikiTitle}>{wikiSummary.title}</p>
                  <p style={S.wikiText}>{wikiSummary.extract}</p>
                  {wikiSummary.url && (
                    <a href={wikiSummary.url} target="_blank" rel="noopener" style={S.panelLink}>
                      Leer en Wikipedia →
                    </a>
                  )}
                </>
              )}
              {!wikiLoading && !wikiSummary && (
                <p style={S.muted}>Sin artículo disponible para este lugar.</p>
              )}
            </div>

          </div>
        )}
      </div>

      {/* Thumbnail strip */}
      {cityCards.length > 1 && (
        <div style={S.strip}>
          {cityCards.map((card, i) => (
            <button
              key={card.objectid}
              onClick={() => goTo(i)}
              title={card.title}
              style={{ ...S.stripBtn, ...(i === routeIndex ? S.stripBtnOn : {}) }}
            >
              {card.image_thumb
                ? <img src={`${base}images/${card.image_thumb}`} alt="" style={S.stripImg} />
                : <span style={S.muted}>{i + 1}</span>
              }
            </button>
          ))}
        </div>
      )}

    </div>
  );
}

const styles = {
  wrap:     { display: 'flex', flexDirection: 'column', gap: '1rem' },
  cityBar:  { display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' },
  label:    { fontSize: '0.72rem', color: '#9a8c7e', textTransform: 'uppercase', letterSpacing: '0.09em' },
  select:   { background: '#1f1c19', border: '1px solid #3a342d', borderRadius: '4px', color: '#f0e8da', padding: '0.38rem 0.75rem', fontSize: '0.875rem', cursor: 'pointer' },
  muted:    { fontSize: '0.78rem', color: '#9a8c7e' },
  mapLayout:{ display: 'grid', gridTemplateColumns: '1fr', gap: '1rem' },
  mapBox:   { height: '460px', borderRadius: '6px', overflow: 'hidden', border: '1px solid #3a342d', background: '#1a1614' },
  panel:    { background: '#1f1c19', border: '1px solid #3a342d', borderRadius: '6px', display: 'flex', flexDirection: 'column', overflow: 'auto', maxHeight: '460px' },
  routeNav: { display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.65rem 1rem', borderBottom: '1px solid #3a342d', flexShrink: 0 },
  navBtn:   { background: 'transparent', border: '1px solid #3a342d', borderRadius: '4px', color: '#f0e8da', padding: '0.2rem 0.55rem', cursor: 'pointer', fontSize: '1rem' },
  navBtnOff:{ opacity: 0.3, cursor: 'not-allowed' },
  panelImg: { width: '100%', height: 'auto', display: 'block', flexShrink: 0 },
  panelBody:{ padding: '0.75rem 1rem', borderBottom: '1px solid #3a342d' },
  panelTitle:{ fontFamily: 'Georgia, serif', fontWeight: 400, fontSize: '0.92rem', lineHeight: 1.4, marginBottom: '0.3rem', color: '#f0e8da' },
  panelDate: { fontSize: '0.75rem', color: '#9a8c7e', marginBottom: '0.5rem' },
  panelDesc: { fontSize: '0.8rem', lineHeight: 1.7, color: '#c8beb2', marginBottom: '0.6rem' },
  panelLink: { fontSize: '0.76rem', color: '#c9964a', textDecoration: 'none' },
  wikiBlock: { padding: '0.75rem 1rem', flex: 1 },
  wikiHead:  { fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.1em', color: '#9a8c7e', marginBottom: '0.5rem' },
  wikiTitle: { fontSize: '0.85rem', fontWeight: 600, color: '#f0e8da', marginBottom: '0.35rem' },
  wikiText:  { fontSize: '0.8rem', lineHeight: 1.7, color: '#c8beb2', marginBottom: '0.5rem' },
  strip:     { display: 'flex', gap: '4px', overflowX: 'auto', padding: '2px 0' },
  stripBtn:  { flexShrink: 0, width: '62px', height: '62px', border: '2px solid transparent', borderRadius: '4px', overflow: 'hidden', padding: 0, cursor: 'pointer', background: '#1f1c19', display: 'flex', alignItems: 'center', justifyContent: 'center' },
  stripBtnOn:{ borderColor: '#c9964a' },
  stripImg:  { width: '100%', height: '100%', objectFit: 'cover', display: 'block' },
};
