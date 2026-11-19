# README-DESIGN

How this profile page is designed, built and maintained.

## Concept: an engineering field journal

The page is a notebook kept by an engineer who experiments, builds and writes things down. It borrows from scientific field journals, topographic maps and editorial print: plates with figure numbers, ruled margins, specimen labels, and one signature drawing, a head and shoulders made of contour lines. It is monochrome on purpose; hierarchy comes from weight, grey value and whitespace, never from colour.

## Design tokens

| Token | Light | Dark | Use |
|---|---|---|---|
| paper | `#F7F7F4` | `#202020` | sheet background |
| paper-2 | `#EEEEEA` | `#2A2A28` | boxes, leaf blade |
| ink | `#191919` | `#F5F5F1` | primary lines and text |
| ink-2 | `#555555` | `#BDBDB6` | secondary text, mid contours |
| muted | `#858585` | `#8C8C86` | annotations, inner contours |
| rule | `#D4D4CF` | `#3C3C39` | hairlines, minor ticks |
| strong | `#A7A7A0` | `#66665F` | frames, major ticks |
| panel / panel text | `#202020` / `#F5F5F1` | `#F7F7F4` / `#191919` | the one inverted block per diagram |

The tokens live in `LIGHT` and `DARK` at the top of `scripts/build_assets.py`. Dark mode swaps the palette and nothing else.

## Typography

- **Display (wordmark):** Latin Modern Roman 10, converted to outlines (`scripts/glyphs.json`), so it looks the same on every device. GitHub cannot load web fonts, and outlines need no font licence at display time; Latin Modern is distributed under the GUST Font License.
- **Serif (plate titles, subtitle):** live text, stack `Iowan Old Style, Palatino Linotype, Palatino, Book Antiqua, Georgia, Times New Roman, serif`.
- **Mono (labels, numbering, metadata):** live text, stack `IBM Plex Mono, JetBrains Mono, SF Mono, ui-monospace, Menlo, Consolas, DejaVu Sans Mono, Liberation Mono, monospace`.
- **Sans:** reserved in the SVG stylesheet; the README body uses GitHub's own sans.

No font is embedded or imported. Every label has slack around it so a different fallback font only shifts widths slightly.

## Graphic language

Contour lines, rulers and tick scales, registration crosshairs, figure and study numbering, specimen captions, thin double page borders, and a small "hill" motif for dividers. Strokes are 0.8 to 1.4 units for linework and 2 to 2.6 for outlines. One diagram element per plate is inverted (the policy network, the classifier, the reranker) to mark the part the study is about.

## Assets

Each asset has a light file and a `-dark` file, selected in the README with `<picture>` and `prefers-color-scheme`.

| File | viewBox | Purpose |
|---|---|---|
| `assets/field-cover.svg` | 760 × 560 | the paper sheet of the header: wordmark, descriptors, rulers |
| `assets/contour-portrait.gif` | 560 × 560 | the animated portrait plate beside the sheet, light theme (dark lines on `#EEEEEA`) |
| `assets/contour-portrait-dark.gif` | 560 × 560 | the same plate for the dark theme (light lines on `#202020`) |
| `assets/portrait-contour.svg` | 520 × 640 | the abstract fallback portrait on a transparent background; not shown while the GIF is in the header |
| `assets/reactor-study.svg` | 1000 × 700 | Study 001 control-loop plate |
| `assets/rice-study.svg` | 1000 × 700 | Study 002 vision and retrieval plate |
| `assets/crm-study.svg` | 1000 × 700 | Study 003 plate: question to records, records to campaign |
| `assets/activity-log.svg` | 1000 × 540 | activity window; ships in a static state, the workflow redraws it from the GitHub API |
| `assets/visual-divider.svg` | 1000 × 40 | section separator |

All are pure SVG: no scripts, no raster images, no external references, a `<title>` and `<desc>` on each. `python scripts/validate.py` checks this and checks that every image the README points to exists.

## Building the assets

```bash
pip install numpy scipy contourpy pillow
python scripts/build_assets.py            # all assets
python scripts/build_assets.py --only portrait cover
python scripts/build_assets.py --out /tmp/test    # build somewhere else
python scripts/build_activity.py --static         # the activity window's no-data state (standard library only)
python scripts/validate.py
```

`scripts/fj.py` holds the palettes and SVG helpers shared by both builders; it uses only the standard library.

The build is deterministic. The portrait is a stylised head-and-shoulders silhouette (a spline through hand-placed points) turned into a field: distance from the edge, plus bumps for the cranium, cheek, eye, jaw, ear and neck, plus slow noise so no two lines match. Equal-interval contours of that field are extracted with `contourpy`, simplified and written as smooth paths in four tones. Change the look by editing `SIL`, the feature list in `portrait_geometry`, the contour `step`, or the seed.

## The header portrait

The header is two images side by side: the animated plate on the left (`assets/contour-portrait.gif` in the light theme, `assets/contour-portrait-dark.gif` in the dark theme, chosen by `<picture>`) and the paper sheet (`field-cover.svg`, with its own dark variant) on the right. Their widths in `README.md` are 42.4% and 57.5%, the ratio of their pixel widths (560 : 760) at the same height of 560, so they scale together and stay the same height on every screen. The plate is on the left because the portrait faces right, into the text; it is never mirrored. The two `<img>` tags sit on one line with no spaces between them, so no gap opens between plate and sheet.

To change a portrait, run `python scripts/prepare_header_gif.py new.gif --theme light` (dark lines on a light background, written to `contour-portrait.gif`) or `--theme dark` (light lines on black, written to `contour-portrait-dark.gif`). It maps the tones to the design tokens (light: ink `#191919` on `#EEEEEA`; dark: `#F5F5F1` on `#202020`), scales the frames to 560 px wide, bottom-aligns them so the bust bleeds off the edge, and keeps the original timing and looping. Each GIF is about 1.8 MB; keep each under 5 MB. `python scripts/validate.py` warns if one grows.

**Going back to a drawn portrait.** `python scripts/build_assets.py --inline-cover` redraws `field-cover.svg` as a single cover with the abstract portrait inside (1200 × 560); replace the two-image header in `README.md` with one `<picture>` of that file at `width="100%"`. To turn a photograph into a static vector contour portrait instead, run `python scripts/portrait_from_photo.py photo.jpg --flip` (a head-and-shoulders photo on a plain light backdrop; `--flip` if you face right; `--crop` and `--mask` are optional), then `python scripts/build_assets.py --only portrait cover --inline-cover`. The script writes only vector paths to `scripts/portrait_override.json`; the photo is not stored. Delete that file to return to the abstract portrait.
## Updating the content

- **Page text and links:** edit `README.md` directly.
- **Plate text:** edit `build_reactor`, `build_rice` and `build_crm` in `scripts/build_assets.py`, then rebuild.
- **New numbers:** add them only when they come from the experiment outputs or the final report, and name the evaluation split next to any accuracy figure.

## Where each claim comes from

| Claim | Source | Status |
|---|---|---|
| 0.5 L jacketed reactor, four states (initiator, monomer, reactor and jacket temperature), RK45 | `batch_reactor_env.py` | verified in code |
| Measurements are reactor and jacket temperature; the UKF estimates the concentrations | `batch_reactor_env.py`, `train_ppo.py` | verified in code |
| PPO, 2 × 256 hidden layers; observation has estimates, temperatures and tracking error | `train_ppo.py` | verified in code |
| Heater current 8 to 20 mA, coolant flow 0 to 0.7 L/min | `train_ppo.py` (latest) and the repo README | verified in code |
| Reward terms: tracking, actuator cooperation, smoothness, barrier at the maximum allowable temperature, estimator confidence | `train_ppo.py` docstring | verified in code |
| 7,200-step reference trajectory | `train_ppo.py` | verified in code |
| SHAP, surrogate decision trees, sensitivity heatmaps | repo README and `explainability/` | from the repo |
| Rice study components (EfficientNet-B3, MMR, cross-encoder reranking, OOD rejection, Kaggle and outdoor images) | project brief | stated, not re-checked against the repo |
| Northstar: the model returns a JSON query plan and never writes SQL; four operations, 27 filter operators; parameterized SELECT-only DuckDB; five safeguards (schema, columns, parameters, SELECT-only, row cap) | `ai-crm-agent` README | from the repo |
| Northstar: per-recipient preview, approval before sending, SendGrid, send summary, audit trail; FastAPI, DuckDB, LangChain with Groq, React, Vercel and Render | `ai-crm-agent` README | from the repo |
| Hackathon results, tools list | resume and repo READMEs | stated by the author |

**Deliberately left out:** tracking within 2 °C, zero thermal runaway, any resilience score, any accuracy percentage, any Recall@K / MRR / faithfulness figure, and the batch duration. The reactor README says a 60-hour batch, but `train_ppo.py` prints the 7,200-step horizon in minutes while the plant model converts flow in L/min to mL/s, so the time unit is ambiguous in the code; the page says "7,200-step" and nothing more.

## To confirm before publishing

- `Rice-shield-AI` is assumed to be the repository for Study 002.
- LinkedIn: three spellings exist (profile, resume, one repository README). The page uses the one on the GitHub profile.
- Email: the resume address is used; the GitHub profile shows a different one.
- The Docker entry in the workbench comes from the resume, not from a repository.

## The activity log: the one automated element

`assets/activity-log.svg` (and `-dark`) is a window with the contributions per month over the past twelve months and the latest commit of each recently pushed public repository. It ships in a **static state** (an index of the five projects and an "awaiting first sync" chart, no numbers), so the page is complete even with automation off.

`.github/workflows/activity.yml` redraws it with `scripts/build_activity.py`:

- **When:** daily, on demand (Actions tab, "field log", Run workflow), and on a push that touches the script, `fj.py` or the workflow. The first push therefore draws it within a minute or two.
- **Data and permissions:** one GraphQL request using the built-in `GITHUB_TOKEN`, so there is no secret to create or leak. The job's only permission is `contents: write`, to commit the two SVGs.
- **Real data only:** contributions are summed per calendar month from GitHub's own calendar (private contributions count only if your profile setting shares them); commit headlines and dates come from each repository's default branch. Nothing is estimated or invented.
- **Rate limits and failures:** rate-limit and server errors are retried with a back-off; if the request still fails, the script exits non-zero without writing anything, so the last good log stays on the page and the failed run is visible in the Actions tab.
- **Deterministic:** the output depends only on the data and the current month, never on a timestamp, so an unchanged log gives identical bytes and no commit.
- **Turning it off:** delete the workflow file or disable it in the Actions tab; the last drawn log stays. GitHub pauses scheduled workflows in a repository with no activity for 60 days; if that happens, run the workflow once by hand.

Test offline with a saved API response: `python scripts/build_activity.py --from-json user.json --today 2026-11-16 --out /tmp/test`.

## Checks that were run

SVG well-formedness and structure (`scripts/validate.py`); the header GIF and sheet rendered side by side in Chromium at 960 px and 390 px to confirm they stay the same height; README rendered with a CommonMark engine and GitHub-like styles in Chromium at 960 px (light and dark) and 390 px; every plate viewed at full size in both palettes; the byte-for-byte rebuild of every asset from the zip; the activity script run offline against a sample API response (layout, monthly sums, ordering, truncation) and in its static state.

**Not run:** the live GitHub API call and the workflow itself, and the page on github.com. Check the first push in both themes, then open the Actions tab: if the "field log" run is green and the window shows your own months and repositories, it works; if it fails, the page keeps the static window.

## Credits

Latin Modern Roman (GUST Font License) for the wordmark outlines. The animated header portraits are the author's own artwork. All drawing code is original. A reference repository was studied for the general approach only (local SVG assets, GitHub-compatible Markdown); none of its code, assets, fonts, wording or layout is reused.
