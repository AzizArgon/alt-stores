// Phase 14: the photo standard as the browser needs it — a copy of backend/app/core/photo_standard.py
// (backend test test_frontend_keeps_the_same_numbers checks they match)
export const PHOTO = {
  CANVAS: 1500, // the 1500×1500 square
  SAFE_ZONE: 0.8, // the product fits into 80% of the side (~10% margin)
  MAX_UPSCALE: 2, // never enlarged more than 2×
  MIN_SIDE: 400, // shorter side below — not accepted
  WARN_SIDE: 1000, // longer side below — "Фото маленькое"
  MAX_SIDE: 6000,
  SOURCE_MAX: 2000, // the browser shrinks to this longest side before sending
  MAX_MB: 8,
  TYPES: ['image/jpeg', 'image/png', 'image/webp'],
  LIMITS: { product: 5, offer: 6, build: 6 },
}
