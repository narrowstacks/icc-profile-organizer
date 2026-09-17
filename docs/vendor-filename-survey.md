# Vendor profile filename survey

What every major paper vendor's ICC download actually looks like on disk,
gathered September 2026 by pulling the profile packages from each vendor's
download page for every printer they list (~14,000 files). This is the
evidence behind the `filename_patterns`, `printer_names` and
`vendor-legends/*.yaml` shipped in `config.yaml`; re-run the fetch described
per vendor when a legend needs refreshing.

Legend for the tables: `<printer>` is the vendor's printer token (see
"Printer tokens"), `<media>` a driver media-type code that the organizer
drops, `<paper>` the part that becomes the paper type.

## Summary

| Vendor | Files | Shape | Printer token examples | Legend source |
| --- | --- | --- | --- | --- |
| Hahnemuehle | 406 sampled (1,547 listed) | `HFA[Photo]_<printer>_<MK\|PK>_<Paper>[_BarytaSetting]` | `EpsSC-P900`, `CanPro1000`, `CanonGP-2600S`, `Canon-PRO2600`, `Can6450` | filename (PR = Photo Rag, FA = Fine Art) |
| Canson Infinity | 353 (2,799 listed) | `cifa_<printer>_<code><weight>[_<m\|p>_bk]` | `p900`, `p7570`, `pixmapro100`, `Can6450`, `iPf_GP4000`, `r2880`, `z3200` | page JSON labels |
| Moab | 1,995 | `MOAB <Paper> <printer> <media>` / `EPSON SC-<model>[_]MOAB <Paper>.emy2` / `PRO-1000_MOAB <Paper>.am1x` | `P900`, `P7570-P9570`, `PRO-100`, `iPF6450`, `PRO-2000`, `Epson 3880` | none needed |
| Red River | 3,007 | `RR <Paper> <Ep\|Can> <printer>[ MK\|PK][ vN]` / `Red River Paper_RR <Paper>.emy2` | `Ep P900`, `EpP900`, `Ep SC-P900`, `Ep 7570-9570`, `Ep SureColor P7570`, `CanPRO-100`, `Canon Pro-100 v2`, `Can iPFX400`, `EpR3000` | product pages (abbreviations) |
| Ilford | 1,318 | `ILFORD_<printer>_<code>[_<variant>]_<media>` (legacy: `n_<code>_<printer>_<media>`) | `EPP700` (P700/P900), `EPSCX500` (P7500/9500), `CANpro-100S`, `CANpro-2_4_6_21_41_61`, `Canpro26_46_6600`, `HPz9` | per-printer table |
| Awagami | 927 | `Awagami_<Paper>_<gsm>_<printer>_<media>` (+ `.am1x`, `EPSON_SC-<model>_Awagami_<Paper>.emy2`) | `P900`, `P7570-9570`, `PRO-100`, `iPFx400`, `PRO-2000-6000`, `non-FP_GP-2000` | filename |
| Breathing Color | 992 | `BC_<Paper>_<printer>_[mk\|pk]_<media>[_-NN]` | `P900`, `P7570`, `PixmaPro100`, `x400`, `Pro2000`, `x900` (=4900/7900/9900) | API product names |
| Innova / Olmec | 1,014 | `Innova_<printer>_<IFAnn>_(<media>)_<MK\|PK>_<quality>` | `Canon_Pro-1000`, `Canon-Pro2000_4000`, `SC-P700_900`, `PixmaPro9500mk2` | item list |
| PermaJet | 1,982 | `[NN.]APJ_<printer>_<Paper>_<media>` | `OEMSCP900`, `EPSONSCP900MK`, `OEMPro100`, `CANONPRO2600`, `EPSONSCP7500-9500` | page JSON |
| Fotospeed | 1,884 | `1FS_<Paper>_<printer>_Generic` (`1FA_` fine art) | `SC-P900`, `P7500`, `Canon-Pro-1000`, `Canon_Pro_2600`, `iPF6400`, `R3000-4K` | filename |
| Epson driver | 82 | `Epson_SC-P900_700_<Paper>` / `SC-P9000_P7000_Series_V <Paper>_MK_v1` / `NNNN.icc` (EMX, name only in desc tag) | `P900_700`, `P9500_7500` | driver |
| Canon driver | 61 | `CN_PRO-2000_520_<Paper>[-P]` | `PRO-2000` | driver |

Across vendors, the paper part is one of: the marketing name in CamelCase
(`PhotoLuster260`), the name with spaces (`Entrada Rag Bright`), a vendor
abbreviation (`PRBaryta`, `UPSatin`, `GPGFS`, `IFA22`, `OLM62`) or an
upper-cased name (`PORTRAITRAG305`). Weights appear as `308`, `110gsm` or
`(75lb)`; the organizer normalises `gsm` away and keeps the number.

## Per vendor

### Hahnemuehle

- Page: <https://www.hahnemuehle.com/en/digital-papers/icc-profile/download-center.html>.
  Three cascading selects; the results come from
  `/de/ajax?tx_altoicc_feajax[action]=ajaxLoadProfiles&tx_altoicc_feajax[printer]=<id>&tx_altoicc_feajax[papergroup]=<1|11|5|2|4|7>`
  (JSON with `result_snippet` HTML). Each `/de/icc-download/dl/<id>.icc` link
  is a ~2.6 MB zip (the ICC plus four language PDFs of printer settings), so
  only a subset was downloaded. Printer ids: 29 entries (Canon PRO-310 … HP Z3200).
- Files: `HFA_CanPro1000_MK_PRBaryta_BarytaSetting.icc`,
  `HFAPhoto_CanPro200_PK_HahnemuehlePhotoGlossy290.icc`,
  `HFA_CanPro2000_MK_Albrecht_Duerer.am1x`, `HFA_EpsSC-P700_MK_PhotoRag.icc`
  (the P700/P900 set is named P700). Abbreviations: `PR` Photo Rag, `FA` Fine
  Art, `ADurer`/`ADuerer`, `WTurner`, `GermEtching`, `MusEtching`,
  `Hemp-Hanf`, `Agave-Sisal`. One stray `PR-UltraSmooth-ab-charge-476910`.
- Also ships `.emx`, `.am1x` and `.oms` (HP) media files with the same stem.

### Canson Infinity

- Page: <https://www.canson-infinity.com/en/icc-profiles>. A Vue app whose
  data is embedded in the page (`ninf_icc_data` JSON: `settings[BRAND][MODEL]`
  → list of `{id, label, media_settings}`). Download is
  `/en/download_icc?icc=<id>-<id>-…&brand=EPSON` → zip containing a PDF and
  `icc/<name>.zip` per paper; those contain the `.icc` plus an `.emy2`/`.am1x`.
  Bundles are 10–46 MB; the server resets connections after ~25 quick
  requests, so pause a few seconds between downloads. 102 printer models.
- Files: `cifa_p900_platine310_p_bk.icc`, `cifa_iPf_GP4000_ragphoto2_310.am1x`,
  `CIFA_R2880_pmk310_M_BK.icc`, `EPSON SC-P900 Canson Infinity_Arches 88.emy2`.
  Codes: `aqua`, `arches88`, `archesbfk_PW`, `baryta2`, `prestige2`,
  `edition2`, `hgloss`, `platine`, `pmk` (PrintMaKing), `ragphoto2`,
  `ragphotd` (Duo), `velin`, `somerset_velvet_white`, `MuseumPro_Lustre`.
  `_m_bk`/`_p_bk` is the ink.

### Moab

- Page: <https://www.moabpaper.com/icc-profiles-downloads>, one Dropbox zip
  per printer (102 zips, ~35 MB each; links are in the page HTML).
- Files: `MOAB Lasal Exhibition Luster P900 PL260.icc`,
  `MOAB Entrada Rag Natural Coldpress PRO-1000 HDFAP.icc`,
  `MOAB Somerset Velvet Epson 3880 VFA.icc`, `MOAB Lasal Photo Matte P900 USFA -10%.icc`,
  `MOAB Moenkopi Kozo P900 Washi Thin.icc`, `EPSON SC-P5300_MOAB Entrada Rag Natural 190.emy2`,
  `PRO-1000_MOAB Slickrock Metallic Silver Pro 300.am1x`. Abbreviations are
  rare (`Somerset Enh Velvet`, `Entrada Nat`/`Brt` in am1x names).

### Red River Paper

- Page: <https://www.redrivercatalog.com/profiles/> → 115 static per-printer
  pages, each linking one zip (`/profiles/epson-p900/Red River Paper Epson
  P700 P900 ICC Profiles v2.1.zip`) or, for old printers, loose `.icc` files.
- Files: `RR UltraPro Satin 4.0 Ep P900.icc`, `RR Palo Duro Matte Canvas P9570 P7570.icc`,
  `RR Polar Matte Canon Pro-100 v2.icc`, `RR UPSatin 4.0 EpR3000.icc`,
  `RR Big Bend Baryta Can iPFX400.icc`, `RR Aurora FA Wht Ep3880 MK.icc`,
  `Red River Paper_RR Pecos Gloss 42lb.emy2`. The most inconsistent vendor:
  `UPSatin`/`UltrProSatn`/`Ult Pro Gloss`, `PaloDuroSat`, `PD SG Rag`,
  `SanGab Fiber`, `Papr Canv`, `Arc Pol Lustr`; the make appears as `Ep`,
  `Epson`, `Can`, `Canon`, `HP`; product versions (`4.0`) are part of the name.

### Ilford

- Page: <https://ilford.com/printer-profiles-paper-settings/> (iframe
  `ilford.com/ilford-profiles/get-related-profiles.php`). Models:
  `POST get-current-printer-models.php post_printer_brand=<canon|epson|hp>`;
  table: `POST multi-load-selected-profiles-via-ajax.php paper_select=<galerie|omnijet studio>&brand_select=…&model_select=…`
  returns rows `<td>Paper name</td><td>filename</td>` — the legend itself.
  57 model entries.
- Files: `ILFORD_EPP700_GPGFS_Baryta.icc`, `ILFORD_CANpro-2_4_6_21_41_61_GTWE_Warm_JPW.icc`,
  `ILFORD_Canpro26_46_6600_GSCSJ_HDFAP.icc`, `ILFORD_HPz9_ONQ5SP10S_PGSGSPLI.icc`
  (Omnijet Studio), legacy `n_GPFAS_CANipf6300_FAPn.icc`, `IGPTC19_EPSC800_USFAPn.icc`,
  `PRO-200_series_ILFORD_IGPSP.am1x`.

### Awagami

- Page: <https://awagami.com/pages/icc-profiles-and-printing-tips>, one
  Shopify-CDN zip per file (1,072 links); the zip name is the file name.
- Files: `Awagami_Bamboo_Paper_110gsm_P7570-9570_VFA.icc`,
  `Awagami_Kozo_Thin_White_PRO-2000-6000_PFAS.icc`,
  `Awagami_Inbe_Thick_White_non-FP_GP-4000.icc` (`FP` = fluorescent pink ink),
  `Awagami_Bizan_Natural_Medium_Handmade_PRO-1100.am1x`,
  `EPSON_SC-P900_Awagami_Premio_Kozo_White.emy2`.

### Breathing Color

- Page: <https://www.breathingcolor.com/pages/icc-profile-instruction>;
  data from `https://app.breathingcolor.com/printertypes/all2?make=<Canon|Epson>`
  and `/dev_printer_types/<id>` (JSON with `icc_name`, `icc_media_type_long`,
  `product_name`). 67 printer models; files served from
  `/system_uploads/iccprofile_file/<name>`.
- Files: `BC_Lyve_P7570_mk_WCRW.zip`, `BC_VibranceBaryta_IPFx400_PK_CPSGP2280.icc`,
  `BC_Silverada_6400_PK_Sp1_-15.icc`, `BC_VibrancePhotoMatte_mk_P7000_WCRW.icm`.
  Product codes: `17M`, `600MT`, `800M`, `Lyve`, `Silverada`, `Crystalline`,
  `Chromata`, `OpticaOne`, `PuraSmooth`, `Vib…`. `x400`/`x900`/`x800` are
  family tokens (Canon iPF x400; Epson 4900/7900/9900; 3800/4800/7800/9800).

### Innova Art / Olmec

- Page: <https://innovaart.com/icc-profiles-1/>; everything via
  `POST /wp-admin/admin-ajax.php action=my_action&task=<subcategorylist|grouplist|itemlist|downloadlist>`
  with `cat_id`/`subcat_id`/`group_id`/`item_id`. `downloadlist` returns the
  file stems; item names carry the legend (`Etching Cotton Rag 315gsm - IFA 22`).
- Files: `Innova_Canon_Pro-1000_IFA22_(HWFAP)_MK_Highest-V2`,
  `Olmec_SC-P700_900_OLM62(EPG)_1440_D55_16bits_V2`,
  `Innova_Canon-Pro2000_4000_IFA49_(PPPG2-280)_PK_highest_v2`, legacy
  `Canon_PixmaPro9500mk2_IFA22`, `iPFx300_IFA36_High`, `IFA-013` spellings.

### PermaJet

- Page: <https://www.permajet.com/icc-profiles/>; the profile table is
  embedded as `var iccdl = {…, profiles: {id: {manuf, model, ink, paper, weight}}}`.
  Zip: `POST /wp-admin/admin-ajax.php` form `action=request_icc_profile_zip&profileIds=<id,id,…>`
  returns the zip directly (one per model, 50 models).
- Files: `APJ_OEMSCP900_TitaniumLustre_PLPP.icc`, `APJ_OEMPro1000_UltraPearl_PSGPP2_280.icc`,
  `40.APJ_EPSONSCP900MK_OEM_WALLARTMATT170_EAM.icc`,
  `APJ_OEM_EPSONSCP7500-9500_BARYTARAG_310_EPSG.icm`. Two generations of
  naming (CamelCase vs upper-case with numeric prefix); the last token is
  always the driver media.

### Fotospeed

- Page: <https://fotospeed.com/profiles/> → `/profiles/printer/ink/ink/<id>/`
  (63 printer/ink pages) → `/media/profiles/profile/<name>.zip`.
- Files: `1FS_PFLustre_SC-P900_Generic.zip`, `1FS_NSTBrightWhite_Canon-Pro1100_Generic.zip`,
  `1FS_ArtSmoothDuo_Canon-Pro-1000-Generic-20-06-22.icc` (date inside the
  zip only), `1FA_PlatinumEtching_iPF6400_Generic.icc`, `1FS_~DCFilm_SC-P9000_Generic.icc`.
  Loose naming: `NST`/`NT` (Natural [Soft] Textured), `HWS` (High White
  Smooth), `PF` range, printer as `Canon_Pro_2600`, `Epson-P700`, `R3000-4K`.

### Epson / Canon driver profiles (this Mac)

- `/Library/Printers/EPSON/InkjetPrinter2/ICCProfiles/*.profiles/Contents/Resources/`:
  `Epson_SC-P900_700_LegacyPlatine.icc`, `EPSON_SC-P9500_7500_PremiumLusterPhotoPaper260.icc`,
  `SC-P9000_P7000_Series_V HotPressBright_MK_v1.icc`.
  `/Library/Printers/EPSON/EMXProf/EPSON_SC_P900_Series/19NN.icc` are EMX
  profiles whose only name is the `desc` tag (`Epson SC-P900_700 Legacy Etching`).
- `/Library/Printers/Canon/BJPrinter/Resources/ICCProfiles/PRO2000.canonicc/Contents/Resources/CN_PRO-2000_520_<Paper>[-P].icc`.

## Printer tokens

Every spelling seen for the printers this repo's owner uses, all mapped in
`printer_names`:

| Printer | Tokens |
| --- | --- |
| Epson P900 (+P700) | `P900`, `SC-P900`, `EpsSC-P900`, `SCP900`, `EPSONSCP900MK`, `EpP900`, `Ep P900`, `P900_700`, `P700`, `EPP700`, `SC-P700_900`, `P700_VFA` |
| Epson P7570 (+P9570, P7500/9500) | `P7570`, `P7570-9570`, `P7570-P9570`, `SC-P7570`, `EpsSC-P7570`, `Ep 7570-9570`, `Ep 7570 9570`, `Ep SureColor P7570`, `P9570 P7570`, `P7500-9500`, `EPSCX500`, `P9500_7500`, `EPSONSCP7500-9500` |
| Canon Pixma PRO-100 | `PRO-100`, `Pro-100`, `pixmapro100`, `PixmaPro100`, `CanPro-100`, `CanPRO-100`, `CanPro100`, `Canon Pro-100 v2`, `CANpro-100S`, `OEMPro100`, `Pro_100` |
| Canon iPF6450 (+6400/8400/9400) | `iPF6450`, `Can6450`, `ipf6450`, `iPF6400`, `IPF6400`, `iPFX400`, `iPFx400`, `x400`, `6400`, `CANipf64_84_9400`, `iPF6400S` |
| Canon imagePROGRAF PRO-2000 (+4000/6000 family) | `PRO-2000`, `Pro2000`, `CanPRO-2000`, `PRO-2000-6000`, `Pro2000_4000`, `Canon-iPF-Pro2000_4000`, `CANpro-2_4_6_21_41_61`, `Canpro2_4_6_21_41_61`, `Pro_2000` |

## Coverage

Running the whole 14,073-file corpus through `config.yaml` (Sept 2026):

| Vendor | Parsed | Unparsed | What is left |
| --- | --- | --- | --- |
| Awagami | 926 | 1 | one `.am1x` without a printer |
| Breathing Color | 961 | 31 | `x100`/`5100` era files with odd tokens |
| Canson | 347 | 6 | Stylus Photo 1400 / R2200 |
| Fotospeed | 1,662 | 222 | consumer printers (G-series, ET-18100 variants, MG/TS) and stray files |
| Hahnemuehle | 406 | 0 | |
| Ilford | 1,147 | 171 | `.am1x`/`.emx` presets and Omnijet legacy names |
| Innova | 799 | 215 | consumer Pixma MG/MP, presets |
| Moab | 1,736 | 259 | `.am1x` presets (`PRO-1000_MOAB …`) and Stylus Pro 4000 |
| PermaJet | 1,953 | 29 | Canon G-series, "HERITAGE" names for old Stylus Pro |
| Red River | 1,684 | 1,323 | consumer Canon/Epson (MG, TS, XP, G, ET) tokens the table does not carry |
| Epson/Canon driver | 171 | 24 | numeric EMX profiles, generic RGB/Gray |

Unparsed here means "printer not in `printer_names`" in nearly every case,
not a naming shape the patterns cannot express; add the alias and the file
parses.
