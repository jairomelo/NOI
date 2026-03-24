/**
 * UI string dictionary — English and Spanish.
 * Card content (titles, descriptions, locations) is translated separately.
 */
export const ui = {
  en: {
    // Language display names
    langNames: {
      it: 'Italian', fr: 'French', de: 'German',
      en: 'English', es: 'Spanish', ru: 'Russian', nl: 'Dutch',
    },
    // ObjectGrid
    sort: 'Sort',
    sortRichnessAsc: 'Monochrome → rich', sortRichnessDesc: 'Rich → monochrome', sortGroup: 'Groups',
    language: 'Language', size: 'Size',
    postcards: n => `${n} postcards`,
    cardBack: n => `${n} — back`,
    // PostcardFlip
    flipToBack:  '↩ Click to see the back',
    flipToFront: '↩ Click to see the front',
    flipTipBack:  'Click to see the back',
    flipTipFront: 'Click to see the front',
    // RouteMap
    place: 'Place:',
    wikiHead: 'Today — Wikipedia',
    wikiLoading: 'Searching…',
    wikiNone: 'No article available for this location.',
    viewFull: 'View full card →',
    readWiki: 'Read on Wikipedia →',
    wikiLang: 'en',
  },
  es: {
    langNames: {
      it: 'Italiano', fr: 'Francés', de: 'Alemán',
      en: 'Inglés', es: 'Español', ru: 'Ruso', nl: 'Neerlandés',
    },
    sort: 'Ordenar',
    sortRichnessAsc: 'Monocromo → rico', sortRichnessDesc: 'Rico → monocromo', sortGroup: 'Grupos',
    language: 'Idioma', size: 'Tamaño',
    postcards: n => `${n} postales`,
    cardBack: n => `${n} — reverso`,
    flipToBack:  '↩ Clic para ver el reverso',
    flipToFront: '↩ Clic para ver el frente',
    flipTipBack:  'Clic para ver el reverso',
    flipTipFront: 'Clic para ver el frente',
    place: 'Lugar:',
    wikiHead: 'Contexto actual — Wikipedia',
    wikiLoading: 'Buscando…',
    wikiNone: 'Sin artículo disponible para este lugar.',
    viewFull: 'Ver objeto completo →',
    readWiki: 'Leer en Wikipedia →',
    wikiLang: 'es',
  },
};
