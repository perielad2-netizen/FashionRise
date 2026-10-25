# WEB-V4J-A — Rear-view artwork specifications (10 models)

**Audience:** ChatGPT image-generation workflow + operator visual review.  
**Forbidden:** horizontal flip/mirror of the front, procedural silhouette inversion, or presenting the front as a rear.  
**Required:** genuine back anatomy (scapulae, spine furrow, glutes, popliteal folds, nape) in the **same** premium blank-face fashion-croquis language as the fronts: clean black outline, light interior construction lines, solid light fill, **transparent** background (not solid black mats).

**Status (2026-10-25):** Specs retained from PR #50 matching work. **No rear images generated or approved.** Do not commit shippable `-back.png` until provenance and per-model (or contact-sheet) operator acceptance are resolved.

**Provenance:** Operator front masters are the pose source of truth but are **not published** in this public repository (redistribution rights unconfirmed). Identify each master via `modelId` + `sha256` in `front-ref-match-report.json`. Brief ChatGPT from operator-held local copies and/or shipped library fronts — do not require binaries from this PR.

Shipped Studio canvas targets (must match for drop-in later):

| Canvas class | Pixel size | Models |
|--------------|------------|--------|
| A | **656×1199** | `female-straight`, `female-hand-hip` |
| B | **900×1200** | remaining eight |

When generating, prefer outputting exactly the **shipped canvas size** with the figure’s content bbox proportionally matching the front (same relative head-to-toe placement and scale). Soft anti-aliased edges OK; no opaque page background.

**Shared style rules (all ten):**

1. Featureless oval head (no face, no hair mass unless the front already implies scalp silhouette only).  
2. Fashion proportions (~9–10 heads), elongated limbs.  
3. Vertical balance / weight distribution must match the front stance (do not “correct” into a T-pose).  
4. Arm and leg crossings are **anatomical rears of the same pose**, not mirrored front drawings.  
5. Interior guides: spine / center back line, shoulder blade hints, waist, hip — lighter than the outer contour.  
6. Hands/feet stylized like the front (heeled/pointed female feet where the front shows them).  
7. Licensing: treat as original companion art derived from operator fronts; do not watermark.

---

## 1. `female-straight` — Standing

| Field | Value |
|-------|-------|
| Front master (private) | `female-straight.front-ref.png` (see manifest sha256; binary not in repo) |
| Upload id | `80f8e22f-3b41-4438-9402-df10553880fb` |
| Target canvas | **656×1199** |
| Content bbox (front ref) | (209, 26)–(526, 1173) · 318×1148 |
| Transparency | ~73% fully transparent; soft partial alpha on edges |

**Front pose summary:** Symmetrical en-face standing pose; arms relaxed slightly off torso; legs parallel, feet together/pointed down; dramatic hourglass; head oval with crosshair.

**Rear specification:**

- Same outer silhouette width at shoulders / waist / hips; feet and hands in corresponding rear foreshortening.  
- Replace bust curves with subtle scapular ovals; keep extreme waist pinch and wide hip flare.  
- Spine as gentle vertical furrow from nape through lumbar; glute separation consistent with closed stance.  
- Arms: show olecranon / back of forearms; fingers still pointing down.  
- Knees: popliteal indication instead of kneecap circles.  
- Head: back of cranium + nape; no hair.

---

## 2. `female-hand-hip` — Hand on hip

| Field | Value |
|-------|-------|
| Front master (private) | `female-hand-hip.front-ref.png` (see manifest sha256; binary not in repo) |
| Upload id | `46294290-d3f2-479c-8729-ae0793613c05` |
| Target canvas | **656×1199** |
| Content bbox | (50, 31)–(494, 1173) · 445×1143 |

**Front pose summary:** Weight on figure’s left leg (viewer’s right); right leg stepped out wide; left hand on hip (elbow sharply out); right arm hanging; head tilted to figure’s right.

**Rear specification:**

- Preserve wide stance and high left hip.  
- Figure’s left hand remains on the hip — from rear, show dorsum of hand / thumb wrap on the iliac crest (viewer’s left).  
- Figure’s right arm hangs; show triceps and back of hand.  
- Scapulae asymmetric with the raised/open left elbow; spine curves with the hip tilt.  
- Standing leg (figure left) reads as supporting from behind; stepped right leg shows calf/Achilles.  
- Do not uncross or narrow the stance.

---

## 3. `female-contrapposto` — Contrapposto

| Field | Value |
|-------|-------|
| Front master (private) | `female-contrapposto.front-ref.png` (see manifest sha256; binary not in repo) |
| Upload id | `97d36898-c87f-4a5d-a9cd-e4d1830a38de` |
| Target canvas | **900×1200** (master briefing 1086×1448) |
| Content bbox (master) | (310, 15)–(752, 1435) · 443×1421 |

**Front pose summary:** Right hand on hip; left arm hanging; legs crossed mid-thigh (figure’s right leg in front); elongated neck; head tilted to figure’s right; X-silhouette.

**Rear specification:**

- Keep crossed-leg silhouette. From behind, the **figure’s right leg** (the front-crossing leg) is nearer the viewer and still passes across the left.  
- Right hand on hip → rear shows back of hand and bent elbow (viewer’s right).  
- Left arm hangs with visible elbow tip.  
- Clear scapular contrast (working right arm vs hanging left); lumbar curve into glutes.  
- Pointed heeled feet remain; do not plant them flat.

---

## 4. `female-cross-ankle` — Crossed ankles

| Field | Value |
|-------|-------|
| Front master (private) | `female-cross-ankle.front-ref.png` (see manifest sha256; binary not in repo) |
| Upload id | `ff660483-1351-4c2d-b02e-cf5bc6e8b445` |
| Target canvas | **900×1200** (master 1086×1448) |
| Content bbox (master) | (391, 26)–(728, 1425) · 338×1400 |

**Front pose summary:** Formal front pose; ankles crossed (figure’s right in front of left); both arms hanging slightly flared; long neck; hourglass; head tilted slightly right.

**Rear specification:**

- Narrow lower silhouette with ankles still crossed — figure’s right foot/ankle remains the forward (nearer) crossing element from behind.  
- Arms: bilateral hanging, show posterior deltoid / triceps, palms orientation consistent with slight external rotation.  
- Soft scapulae + continuous spine; glutes and calves defined but not bodybuilder-heavy.  
- Maintain the same head tilt direction relative to the body.

---

## 5. `female-atelier` — Atelier

| Field | Value |
|-------|-------|
| Front master (private) | `female-atelier.front-ref.png` (see manifest sha256; binary not in repo) |
| Upload id | `44f151fe-f5bb-48ce-849e-3a79963bf6e5` |
| Target canvas | **900×1200** (master 1086×1448) |
| Content bbox (master) | (334, 27)–(788, 1428) · 455×1402 |

**Front pose summary:** Slight contrapposto; figure’s right hand on hip; left arm down; left leg crosses in front at upper thigh; left shoulder slightly higher; head tilted toward figure’s right.

**Rear specification:**

- Match elevated left shoulder and hip counter-tilt.  
- Crossed legs: from rear, figure’s **left** leg is the nearer crossing leg.  
- Right hand on hip visible from behind (viewer’s right).  
- Spine S-curve matches the front’s torso twist; scapula on the working-arm side more pronounced.  
- Keep long tapering legs and pointed feet.

---

## 6. `female-cross-leg` — Crossed leg

| Field | Value |
|-------|-------|
| Front master (private) | `female-cross-leg.front-ref.png` (see manifest sha256; binary not in repo) |
| Upload id | `80663d57-43b8-4005-8f64-c75c0e7883c7` |
| Target canvas | **900×1200** (master 1086×1448) |
| Content bbox (master) | (370, 25)–(747, 1422) · 378×1398 |

**Front pose summary:** Runway walk energy; figure’s right leg crosses in front of left; both arms gently away from torso; hips tilted; hourglass; pointed feet (front foot slightly higher).

**Rear specification:**

- Walking/cross silhouette preserved; figure’s right leg nearer when viewed from behind.  
- Arms hang with soft elbow bend — show posterior arm planes, not front biceps contour.  
- Glute and calf definition support the stride; Achilles on the trailing foot.  
- Head oval from behind with same slight downward/forward attitude.

---

## 7. `male-straight` — Standing

| Field | Value |
|-------|-------|
| Front master (private) | `male-straight.front-ref.png` (see manifest sha256; binary not in repo) |
| Upload id | `d02c0b5e-5882-4786-8861-8ba3ddce1ea7` |
| Target canvas | **900×1200** (master 1086×1448) |
| Content bbox (master) | (356, 12)–(729, 1433) · 374×1422 |

**Front pose summary:** Neutral symmetrical male standing; V-taper; arms at sides; legs close; muscular but fashion-elongated; featureless head.

**Rear specification:**

- Mirror the V-taper via lat width + narrow waist — do **not** redraw as a bulkier powerlifter back.  
- Symmetrical scapulae, spinal furrow, defined glutes and gastrocnemius.  
- Arms show triceps / posterior deltoid; hands still mid-thigh.  
- Feet: rear/heel indication consistent with pointed/down front feet.

---

## 8. `male-step` — Step

| Field | Value |
|-------|-------|
| Front master (private) | `male-step.front-ref.png` (see manifest sha256; binary not in repo) |
| Upload id | `118c5f39-563c-4598-b266-4ee419320c66` |
| Target canvas | **900×1200** (master 1086×1448) |
| Content bbox (master) | (347, 14)–(752, 1434) · 406×1421 |

**Front pose summary:** Subtle walk; figure’s right leg forward (weight); left leg back, foot angled out; arms hanging slightly flared; athletic V-taper.

**Rear specification:**

- Same stride: from behind, figure’s **right** leg is forward (appears toward viewer’s right), left trails (viewer’s left).  
- Posterior chain emphasis on the trailing leg; supporting glute on the forward side.  
- Arms relaxed; avoid flipping which arm is which.  
- Keep head tilt / oval scale identical.

---

## 9. `male-walk` — Walk

| Field | Value |
|-------|-------|
| Front master (private) | `male-walk.front-ref.png` (see manifest sha256; binary not in repo) |
| Upload id | `1ef9f89e-f778-48ae-823c-99d9fc4d3a0d` |
| Target canvas | **900×1200** (master 1086×1448) |
| Content bbox (master) | (348, 13)–(738, 1436) · 391×1424 |

**Front pose summary:** Stronger walk; figure’s **left** leg forward and slightly crossing center; right leg trailing; arms at sides; muscular fashion proportions.

**Rear specification:**

- Stride orientation opposite to `male-step`: from behind, figure’s **left** leg is the forward/crossing leg (viewer’s left), right trails (viewer’s right).  
- Show clear weight shift in glutes/calves; spine vertical with slight walk twist.  
- Hands remain near thighs; fingers slightly curled as in front.  
- Do not reuse the `male-step` rear — foot angles differ.

---

## 10. `male-contrapposto` — Contrapposto

| Field | Value |
|-------|-------|
| Front master (private) | `male-contrapposto.front-ref.png` (see manifest sha256; binary not in repo) |
| Upload id | `32fc6040-4c26-4a1d-9802-1f5c860b82e1` |
| Target canvas | **900×1200** (master 1086×1448) |
| Content bbox (master) | (370, 15)–(784, 1437) · 415×1423 |

**Front pose summary:** Dynamic walk/contrapposto; figure’s right leg forward-out; left trails; right arm hanging; **left arm bent** with hand near upper thigh; broad shoulders; head tilted slightly to figure’s right.

**Rear specification:**

- Preserve bent **left** arm (from behind: viewer’s left shows flexed elbow / dorsal forearm near hip).  
- Right arm hangs long (viewer’s right).  
- Leg relationship: figure’s right leg forward → from behind it sits toward viewer’s right; trailing left toward viewer’s left.  
- Scapular asymmetry: more open on the bent-arm side; strong but elegant lat taper.  
- Maintain fashion elongation — not a mirrored front contour dump.

---

## Delivery checklist for generated rears

For each of the ten IDs, deliver:

1. PNG with **alpha transparency** (no black matte).  
2. Exact target canvas size (656×1199 or 900×1200).  
3. Filename proposal: `<modelId>-back.png` (implementation will place under `/models/library/`).  
4. Side-by-side contact sheet vs front for operator approval (optional but recommended).  
5. Explicit confirmation that the image was **not** produced by flipping the front.

Operator rejects any rear that reads as a mirrored front or breaks stance/arm/leg relationships above.
