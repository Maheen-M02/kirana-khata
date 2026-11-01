AnekDevanagari-Latin-wdth-wght.woff2: Anek Devanagari variable (wght 100-800, wdth 75-125) by Ek Type, SIL OFL 1.1 (see AnekDevanagari-OFL.txt).
Subset to Basic Latin, Latin-1, common punctuation and the rupee sign (U+20B9) with
  pyftsubset "AnekDevanagari[wdth,wght].ttf" --unicodes=U+0020-007E,U+00A0-00FF,U+0131,U+0152-0153,U+02C6,U+02DA,U+02DC,U+2013-2014,U+2018-201A,U+201C-201E,U+2022,U+2026,U+20B9,U+2212,U+00D7 --layout-features="*" --flavor=woff2
Devanagari text deliberately falls back to the system font (Noto Sans Devanagari on Android) to keep the page light.
