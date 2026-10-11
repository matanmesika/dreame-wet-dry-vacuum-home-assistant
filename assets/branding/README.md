# Dreame branding asset provenance

The source SVG in this directory is a third-party Dreame-branded vector
representation from [RiDDiX/home-assistant-matter-hub](https://github.com/RiDDiX/home-assistant-matter-hub/blob/main/packages/frontend/src/assets/brands/Dreame.svg)
(Apache-2.0 repository). The Dreame name, logo and trademark belong to
Dreame Technology. No affiliation, approval or endorsement is implied.

PNG icon and logo variants for Home Assistant are generated using
`python scripts/generate_dreame_brand.py`. The script crops only the Dreame
emblem for square icons and uses the wordmark for landscape logos. Generated
images belong **exclusively** under
`custom_components/dreame_wet_dry_vacuum/brand/`, never within the
standalone Lovelace dashboard.

Normal-resolution icon: 256 x 256; icon@2x: 512 x 512.
Normal-resolution logo: transparent PNG with a 256 px height; @2x: 512 px height.
No HACS storefront icon behavior is guaranteed by local Home Assistant branding:
see https://github.com/hacs/integration/issues/5402.
