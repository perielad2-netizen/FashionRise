using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Content;
using FashionRise.Core.Navigation;
using FashionRise.UI;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>
    /// Create Real Design output — a printed-style FASHION TECHNICAL SPECIFICATION sheet:
    /// header block, front/back flats, sample size base, materials &amp; notions, pattern
    /// pieces, cutting layout and construction order. Measurements are a first draft.
    /// </summary>
    public sealed class TechPackScreen : ScreenBase
    {
        FashionRiseTheme _t = null!;
        Text _styleLine = null!;
        Text _garmentLine = null!;
        RectTransform _sheet = null!;
        RawImage _front = null!;
        RawImage _back = null!;
        Texture2D? _ownedFront;
        Texture2D? _ownedBack;
        FrAiLoadingFx? _loading;
        bool _built;

        public override ScreenId Id => ScreenId.TechPack;

        void Awake()
        {
            _t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", _t);
            _loading = FrAiLoadingFx.Create(root, _t);

            BuildHeader(root);
            BuildBottomBar(root);
            BuildSheetScroll(root);
        }

        void BuildHeader(RectTransform root)
        {
            var top = new GameObject("Top", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var rt = top.GetComponent<RectTransform>();
            rt.SetParent(root, false);
            rt.anchorMin = new Vector2(0f, 1f);
            rt.anchorMax = new Vector2(1f, 1f);
            rt.pivot = new Vector2(0.5f, 1f);
            rt.sizeDelta = new Vector2(0f, 96f);
            var v = top.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(20, 20, 14, 4);
            v.spacing = 1f;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;

            var title = FrUiFactory.AddLabel(top.transform, "H",
                FrUiFactory.Space("Fashion Technical Specification"), _t,
                Mathf.RoundToInt(_t.SubtitleSize), FontStyle.Normal, TextAnchor.MiddleCenter);
            title.font = FrUiFonts.UiMedium;
            FrUiFactory.AddHairline(top.transform, _t);
            _styleLine = FrUiFactory.AddLabel(top.transform, "Style", "STYLE NO.  FW-001", _t,
                Mathf.RoundToInt(_t.CaptionSize), FontStyle.Normal, TextAnchor.MiddleCenter, true);
            _garmentLine = FrUiFactory.AddLabel(top.transform, "Garment", "", _t,
                Mathf.RoundToInt(_t.CaptionSize), FontStyle.Normal, TextAnchor.MiddleCenter, true);
        }

        void BuildBottomBar(RectTransform root)
        {
            const float h = 104f;
            var bottom = new GameObject("Bottom", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var rt = bottom.GetComponent<RectTransform>();
            rt.SetParent(root, false);
            rt.anchorMin = new Vector2(0f, 0f);
            rt.anchorMax = new Vector2(1f, 0f);
            rt.pivot = new Vector2(0.5f, 0f);
            rt.sizeDelta = new Vector2(0f, h);
            var v = bottom.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(18, 18, 4, 12);
            v.spacing = 6f;
            v.childAlignment = TextAnchor.LowerCenter;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;

            var note = FrUiFactory.AddLabel(bottom.transform, "Disc",
                "First production draft — edit measurements, fabric and pattern before manufacturing.",
                _t, Mathf.RoundToInt(_t.OverlineSize + 1f), FontStyle.Normal, TextAnchor.MiddleCenter, true);
            var noteLe = note.GetComponent<LayoutElement>();
            noteLe.minHeight = 16f;
            noteLe.preferredHeight = 18f;

            var row = new GameObject("Actions", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            row.transform.SetParent(bottom.transform, false);
            var rowLe = row.GetComponent<LayoutElement>();
            rowLe.minHeight = 46f;
            rowLe.preferredHeight = 46f;
            var rowH = row.GetComponent<HorizontalLayoutGroup>();
            rowH.spacing = 8f;
            rowH.childForceExpandWidth = true;
            rowH.childControlWidth = true;
            rowH.childControlHeight = true;

            FrUiFactory.AddButton(row.transform, "Export spec", _t, ExportSpec, FrButtonEmphasis.Primary);
            FrUiFactory.AddButton(row.transform, "Regenerate", _t, () => { _ = RegenerateAsync(); });
            FrUiFactory.AddButton(row.transform, "Back", _t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ConceptResult);
            }, FrButtonEmphasis.Ghost);
        }

        void BuildSheetScroll(RectTransform root)
        {
            var scrollGo = new GameObject("Scroll", typeof(RectTransform), typeof(ScrollRect), typeof(RectMask2D));
            var scrollRt = scrollGo.GetComponent<RectTransform>();
            scrollRt.SetParent(root, false);
            scrollRt.anchorMin = Vector2.zero;
            scrollRt.anchorMax = Vector2.one;
            scrollRt.offsetMin = new Vector2(14f, 108f);
            scrollRt.offsetMax = new Vector2(-14f, -100f);

            var content = new GameObject("Sheet", typeof(RectTransform), typeof(VerticalLayoutGroup),
                typeof(ContentSizeFitter));
            _sheet = content.GetComponent<RectTransform>();
            _sheet.SetParent(scrollRt, false);
            _sheet.anchorMin = new Vector2(0f, 1f);
            _sheet.anchorMax = new Vector2(1f, 1f);
            _sheet.pivot = new Vector2(0.5f, 1f);
            _sheet.sizeDelta = Vector2.zero;
            var v = content.GetComponent<VerticalLayoutGroup>();
            v.padding = new RectOffset(0, 0, 0, 24);
            v.spacing = 12f;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;
            content.GetComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;

            var scroll = scrollGo.GetComponent<ScrollRect>();
            scroll.content = _sheet;
            scroll.viewport = scrollRt;
            scroll.horizontal = false;
            scroll.vertical = true;
            scroll.movementType = ScrollRect.MovementType.Elastic;
            scroll.scrollSensitivity = 34f;
        }

        public override async Task ShowAsync(object? payload = null, CancellationToken cancellationToken = default)
        {
            gameObject.SetActive(true);
            if (string.IsNullOrWhiteSpace(App.CreateDesign.LastTechPackJson))
            {
                await GenerateAsync(cancellationToken).ConfigureAwait(true);
                return;
            }

            RenderSheet();
            await LoadFlatsAsync(cancellationToken).ConfigureAwait(true);
        }

        async Task RegenerateAsync()
        {
            App.CreateDesign.ClearTechPack();
            await GenerateAsync(CancellationToken.None).ConfigureAwait(true);
        }

        async Task GenerateAsync(CancellationToken cancellationToken)
        {
            _loading?.Show("Reading your look…");
            try
            {
                var sketch = App.CreateDesign.LastInkImagePath;
                if (string.IsNullOrEmpty(sketch))
                {
                    var raw = App.CreateDesign.SketchReference?.Trim() ?? "";
                    sketch = raw.StartsWith("file:", StringComparison.OrdinalIgnoreCase) ? raw.Substring(5) : raw;
                }

                var result = await App.TechPack.GenerateAsync(new Domain.TechPackRequest
                {
                    DesignId = App.CreateDesign.PersistedDesignId,
                    Notes = App.CreateDesign.LastSketchSummary,
                    LocalSketchForVision = sketch,
                    PolishedImageUrl = App.CreateDesign.LastPolishedImageUrl,
                    FabricName = App.CreateDesign.SketchFabricName,
                    ColorName = App.CreateDesign.SketchColorName,
                    MaterialPairs = App.CreateDesign.SketchMaterialPairs,
                    OnJobStarted = id =>
                    {
                        App.CreateDesign.LastTechPackJobId = id;
                        _loading?.SetStatus("Drafting pattern pieces & measurements…");
                    }
                }, cancellationToken).ConfigureAwait(true);

                App.CreateDesign.LastTechPackJobId = result.JobId;
                App.CreateDesign.LastTechPackJson = result.RawJson;
                App.CreateDesign.LastTechPackFrontImageUrl = result.FrontImageUrl;
                App.CreateDesign.LastTechPackBackImageUrl = result.BackImageUrl;
                App.CreateDesign.LastTechPackPatternImageUrl = result.PatternImageUrl;

                RenderSheet();
                await LoadFlatsAsync(cancellationToken).ConfigureAwait(true);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"FashionRise tech pack failed: {ex}");
                ClearSheet();
                var card = FrUiFactory.AddSpecCard(_sheet, "Could not build tech pack", _t);
                FrUiFactory.AddSpecParagraph(card, ex.Message, _t);
                FrUiFactory.AddSpecParagraph(card,
                    "Check that the API is running on :8001 and you are signed in, then tap Regenerate.", _t);
            }
            finally
            {
                _loading?.Hide();
            }
        }

        void ClearSheet()
        {
            for (var i = _sheet.childCount - 1; i >= 0; i--)
                Destroy(_sheet.GetChild(i).gameObject);
            _built = false;
        }

        void RenderSheet()
        {
            ClearSheet();
            var json = App.CreateDesign.LastTechPackJson;
            if (string.IsNullOrWhiteSpace(json))
                return;

            JObject root;
            try
            {
                root = JObject.Parse(json);
            }
            catch (Exception ex)
            {
                var card = FrUiFactory.AddSpecCard(_sheet, "Raw result", _t);
                FrUiFactory.AddSpecParagraph(card, ex.Message + "\n\n" + json, _t);
                return;
            }

            var garment = root["garment"] as JObject;
            var garmentType = Str(garment?["type"], "Garment");
            _garmentLine.text = "GARMENT   " + garmentType.ToUpperInvariant();
            _styleLine.text = "STYLE NO.  FR-" + ShortCode(App.CreateDesign.LastTechPackJobId);

            BuildDesignCard(root, garment, garmentType);
            BuildFlatsCard();
            BuildMeasurementsCard(root);
            BuildMaterialsCard(root);
            BuildPatternCard(root);
            BuildCuttingCard(root);
            BuildConstructionCard(root);
            _built = true;
        }

        void BuildDesignCard(JObject root, JObject? garment, string garmentType)
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Design", _t);
            FrUiFactory.AddSpecRow(card, "Garment", garmentType, _t);
            if (garment != null)
            {
                AddIfPresent(card, "Silhouette", garment["silhouette"]);
                AddIfPresent(card, "Neckline", garment["neckline"]);
                AddIfPresent(card, "Sleeves", garment["sleeves"]);
                AddIfPresent(card, "Closure", garment["closure"]);
            }

            var fabric = App.CreateDesign.SketchFabricName;
            if (!string.IsNullOrWhiteSpace(fabric))
                FrUiFactory.AddSpecRow(card, "Studio fabric", fabric, _t);
            var color = App.CreateDesign.SketchColorName;
            if (!string.IsNullOrWhiteSpace(color))
                FrUiFactory.AddSpecRow(card, "Studio colour", color, _t);

            var description = Str(garment?["construction_description"], "");
            if (string.IsNullOrEmpty(description))
                description = Str(root["summary"], "");
            if (!string.IsNullOrEmpty(description))
            {
                FrUiFactory.AddSpecBandRow(card, "Description", _t);
                FrUiFactory.AddSpecParagraph(card, description, _t);
            }
        }

        void BuildFlatsCard()
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Technical flats", _t);
            var row = new GameObject("Flats", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            row.transform.SetParent(card, false);
            var le = row.GetComponent<LayoutElement>();
            le.minHeight = 300f;
            le.preferredHeight = 340f;
            var h = row.GetComponent<HorizontalLayoutGroup>();
            h.padding = new RectOffset(10, 10, 10, 10);
            h.spacing = 10f;
            h.childForceExpandWidth = true;
            h.childControlWidth = true;
            h.childControlHeight = true;
            h.childForceExpandHeight = true;

            _front = MakeFlatPane(row.transform, "Front view");
            _back = MakeFlatPane(row.transform, "Back view");
        }

        RawImage MakeFlatPane(Transform parent, string caption)
        {
            var pane = new GameObject(caption, typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            pane.transform.SetParent(parent, false);
            pane.GetComponent<Image>().color = Color.white;
            var edge = pane.AddComponent<Outline>();
            edge.effectColor = new Color(_t.PrimaryText.r, _t.PrimaryText.g, _t.PrimaryText.b, 0.2f);
            edge.effectDistance = new Vector2(1f, -1f);
            pane.GetComponent<LayoutElement>().flexibleWidth = 1f;

            var capGo = new GameObject("Cap", typeof(Text));
            capGo.transform.SetParent(pane.transform, false);
            var cap = capGo.GetComponent<Text>();
            cap.font = FrUiFonts.UiMedium;
            cap.text = FrUiFactory.Space(caption.ToUpperInvariant());
            cap.fontSize = Mathf.RoundToInt(_t.OverlineSize);
            cap.color = _t.SecondaryText;
            cap.alignment = TextAnchor.UpperCenter;
            var capRt = capGo.GetComponent<RectTransform>();
            capRt.anchorMin = new Vector2(0f, 1f);
            capRt.anchorMax = new Vector2(1f, 1f);
            capRt.pivot = new Vector2(0.5f, 1f);
            capRt.sizeDelta = new Vector2(0f, 20f);
            capRt.anchoredPosition = new Vector2(0f, -6f);

            var imgGo = new GameObject("Img", typeof(RectTransform), typeof(RawImage), typeof(AspectRatioFitter));
            var rt = imgGo.GetComponent<RectTransform>();
            rt.SetParent(pane.transform, false);
            rt.anchorMin = new Vector2(0.5f, 0f);
            rt.anchorMax = new Vector2(0.5f, 1f);
            rt.pivot = new Vector2(0.5f, 0.5f);
            rt.offsetMin = new Vector2(0f, 8f);
            rt.offsetMax = new Vector2(0f, -26f);
            var raw = imgGo.GetComponent<RawImage>();
            raw.texture = Texture2D.whiteTexture;
            raw.color = Color.white;
            var fit = imgGo.GetComponent<AspectRatioFitter>();
            fit.aspectMode = AspectRatioFitter.AspectMode.HeightControlsWidth;
            fit.aspectRatio = 0.7f;

            var placeholder = new GameObject("Pending", typeof(Text));
            placeholder.transform.SetParent(pane.transform, false);
            var ph = placeholder.GetComponent<Text>();
            ph.font = FrUiFonts.Ui;
            ph.text = "flat pending";
            ph.fontSize = Mathf.RoundToInt(_t.OverlineSize);
            ph.color = new Color(_t.SecondaryText.r, _t.SecondaryText.g, _t.SecondaryText.b, 0.7f);
            ph.alignment = TextAnchor.MiddleCenter;
            var phRt = placeholder.GetComponent<RectTransform>();
            phRt.anchorMin = Vector2.zero;
            phRt.anchorMax = Vector2.one;
            phRt.offsetMin = Vector2.zero;
            phRt.offsetMax = Vector2.zero;
            return raw;
        }

        void BuildMeasurementsCard(JObject root)
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Sample size base", _t);
            var m = root["measurements"] as JObject;
            FrUiFactory.AddSpecRow(card, "Sample size", Str(m?["sample_size"], "EU 36 / US 4"), _t);

            FrUiFactory.AddSpecBandRow(card, "Body measurements", _t);
            AddMeasurementRows(card, m?["body"] as JObject);

            FrUiFactory.AddSpecBandRow(card, "Finished garment measurements", _t);
            AddMeasurementRows(card, m?["finished"] as JObject);
        }

        void AddMeasurementRows(Transform card, JObject? obj)
        {
            if (obj == null)
            {
                FrUiFactory.AddSpecParagraph(card, "Not provided.", _t);
                return;
            }

            foreach (var p in obj.Properties())
            {
                var value = p.Value?.ToString() ?? "";
                if (string.IsNullOrWhiteSpace(value))
                    continue;
                FrUiFactory.AddSpecRow(card, PrettyKey(p.Name), FormatCm(p.Name, value), _t);
            }
        }

        void BuildMaterialsCard(JObject root)
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Materials & notions", _t);
            FrUiFactory.AddSpecRow3(card, "Item", "Specification", "Qty", _t, header: true);
            if (root["materials"] is not JArray materials || materials.Count == 0)
            {
                FrUiFactory.AddSpecParagraph(card, "No materials returned.", _t);
                return;
            }

            foreach (var mat in materials)
            {
                var name = Str(mat["name"], "Item");
                var role = Str(mat["role"], "");
                if (!string.IsNullOrEmpty(role))
                    name += "\n" + role;
                var spec = Str(mat["recommendation"], "");
                var notes = Str(mat["notes"], "");
                if (!string.IsNullOrEmpty(notes))
                    spec = string.IsNullOrEmpty(spec) ? notes : spec + "\n" + notes;
                var qty = mat["quantity_m"];
                var qtyText = qty == null || qty.Type == JTokenType.Null
                    ? "1 pc"
                    : qty.ToObject<float>().ToString("0.##", CultureInfo.InvariantCulture) + " m";
                FrUiFactory.AddSpecRow3(card, name, spec, qtyText, _t);
            }
        }

        void BuildPatternCard(JObject root)
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Pattern pieces", _t);
            FrUiFactory.AddSpecRow3(card, "Piece", "Grain / notches", "Size", _t, header: true);
            if (root["pattern_pieces"] is not JArray pieces || pieces.Count == 0)
            {
                FrUiFactory.AddSpecParagraph(card, "No pattern pieces returned.", _t);
                return;
            }

            foreach (var p in pieces)
            {
                var name = Str(p["name"], "Piece");
                var qty = p["qty"]?.ToString();
                if (!string.IsNullOrEmpty(qty))
                    name += "\ncut " + qty;

                var detail = new StringBuilder();
                var grain = Str(p["grainline"], "");
                if (!string.IsNullOrEmpty(grain))
                    detail.Append("Grain: ").Append(grain);
                if (p["on_fold"]?.Type == JTokenType.Boolean && p["on_fold"]!.ToObject<bool>())
                    detail.Append(detail.Length > 0 ? " · " : "").Append("place on fold");
                if (p["notches"] is JArray notches && notches.Count > 0)
                {
                    var list = new List<string>();
                    foreach (var n in notches)
                        list.Add(n.ToString());
                    detail.Append(detail.Length > 0 ? "\n" : "").Append("Notches: ").Append(string.Join(", ", list));
                }

                var sa = p["seam_allowance_cm"];
                if (sa != null && sa.Type != JTokenType.Null)
                    detail.Append(detail.Length > 0 ? "\n" : "")
                        .Append("SA ")
                        .Append(sa.ToObject<float>().ToString("0.#", CultureInfo.InvariantCulture))
                        .Append(" cm");

                var w = FirstNumber(p, "approx_w_cm", "width_cm");
                var hgt = FirstNumber(p, "approx_h_cm", "height_cm");
                var size = w != null && hgt != null
                    ? $"{w.Value:0.#} × {hgt.Value:0.#} cm"
                    : "—";

                FrUiFactory.AddSpecRow3(card, name, detail.ToString(), size, _t);
            }
        }

        void BuildCuttingCard(JObject root)
        {
            var cutting = root["cutting_layout"] as JObject;
            if (cutting == null)
                return;
            var card = FrUiFactory.AddSpecCard(_sheet, "Cutting layout", _t);
            var width = cutting["fabric_width_cm"];
            FrUiFactory.AddSpecRow(card, "Fabric width",
                width == null || width.Type == JTokenType.Null
                    ? "150 cm"
                    : width.ToObject<float>().ToString("0.#", CultureInfo.InvariantCulture) + " cm", _t);
            var notes = Str(cutting["notes"], "");
            if (!string.IsNullOrEmpty(notes))
                FrUiFactory.AddSpecParagraph(card, notes, _t);
            var tip = Str(cutting["efficiency_tip"], "");
            if (!string.IsNullOrEmpty(tip))
                FrUiFactory.AddSpecParagraph(card, "Tip: " + tip, _t);
        }

        void BuildConstructionCard(JObject root)
        {
            var card = FrUiFactory.AddSpecCard(_sheet, "Construction order", _t);
            if (root["construction_steps"] is not JArray steps || steps.Count == 0)
            {
                FrUiFactory.AddSpecParagraph(card, "No construction steps returned.", _t);
                return;
            }

            var i = 1;
            foreach (var s in steps)
            {
                var text = s.ToString().Trim();
                if (string.IsNullOrEmpty(text))
                    continue;
                FrUiFactory.AddSpecRow(card, i + ".  " + text, "", _t);
                i++;
            }
        }

        void AddIfPresent(Transform card, string label, JToken? token)
        {
            var value = Str(token, "");
            if (!string.IsNullOrEmpty(value))
                FrUiFactory.AddSpecRow(card, label, value, _t);
        }

        static float? FirstNumber(JToken parent, params string[] keys)
        {
            foreach (var k in keys)
            {
                var t = parent[k];
                if (t != null && t.Type != JTokenType.Null &&
                    float.TryParse(t.ToString(), NumberStyles.Any, CultureInfo.InvariantCulture, out var v))
                    return v;
            }

            return null;
        }

        static string Str(JToken? token, string fallback)
        {
            if (token == null || token.Type == JTokenType.Null)
                return fallback;
            var s = token.ToString().Trim();
            return string.IsNullOrEmpty(s) ? fallback : s;
        }

        static string PrettyKey(string key)
        {
            var clean = key.Replace("_cm", "").Replace('_', ' ').Trim();
            if (clean.Length == 0)
                return key;
            return char.ToUpperInvariant(clean[0]) + clean.Substring(1);
        }

        static string FormatCm(string key, string value) =>
            key.EndsWith("_cm", StringComparison.OrdinalIgnoreCase) &&
            !value.EndsWith("cm", StringComparison.OrdinalIgnoreCase)
                ? value + " cm"
                : value;

        static string ShortCode(string jobId)
        {
            if (string.IsNullOrWhiteSpace(jobId))
                return "001";
            var clean = jobId.Replace("-", "");
            return clean.Length <= 4 ? clean.ToUpperInvariant() : clean.Substring(0, 4).ToUpperInvariant();
        }

        void ExportSpec()
        {
            var json = App.CreateDesign.LastTechPackJson;
            if (string.IsNullOrWhiteSpace(json))
                return;

            try
            {
                var dir = Path.Combine(UnityEngine.Application.persistentDataPath, "TechPacks");
                Directory.CreateDirectory(dir);
                var path = Path.Combine(dir, $"techpack_{DateTime.UtcNow:yyyyMMdd_HHmmss}.json");
                File.WriteAllText(path, json);
                if (!NativeShareSheet.TryShareText("FashionRise tech pack: " + path, "FashionRise tech pack"))
                    ShareClipboard.Copy(json);
                Debug.Log($"FashionRise tech pack exported to {path}");
            }
            catch (Exception ex)
            {
                ShareClipboard.Copy(json);
                Debug.LogWarning($"FashionRise tech pack export fell back to clipboard: {ex.Message}");
            }
        }

        async Task LoadFlatsAsync(CancellationToken ct)
        {
            if (!_built)
                return;
            var front = await LoadFlatAsync(_front, _ownedFront, App.CreateDesign.LastTechPackFrontImageUrl, ct)
                .ConfigureAwait(true);
            if (front != null)
                _ownedFront = front;
            var back = await LoadFlatAsync(_back, _ownedBack, App.CreateDesign.LastTechPackBackImageUrl, ct)
                .ConfigureAwait(true);
            if (back != null)
                _ownedBack = back;
        }

        async Task<Texture2D?> LoadFlatAsync(RawImage target, Texture2D? previous, string url, CancellationToken ct)
        {
            if (target == null || string.IsNullOrWhiteSpace(url))
                return null;
            try
            {
                using var req = UnityWebRequestTexture.GetTexture(RewriteToApiHost(url));
                var op = req.SendWebRequest();
                while (!op.isDone)
                    await Task.Delay(32, ct).ConfigureAwait(true);
                if (req.result != UnityWebRequest.Result.Success)
                    return null;
                var tex = DownloadHandlerTexture.GetContent(req);
                if (tex == null)
                    return null;
                if (previous != null)
                    Destroy(previous);
                target.texture = tex;
                var fit = target.GetComponent<AspectRatioFitter>();
                if (fit != null && tex.height > 0)
                    fit.aspectRatio = tex.width / (float)tex.height;
                var pending = target.transform.parent.Find("Pending");
                if (pending != null)
                    pending.gameObject.SetActive(false);
                return tex;
            }
            catch
            {
                return null;
            }
        }

        string RewriteToApiHost(string url)
        {
            if (string.IsNullOrWhiteSpace(url) || string.IsNullOrWhiteSpace(App.ApiBaseUrl))
                return url;
            try
            {
                var apiUri = new Uri(App.ApiBaseUrl.TrimEnd('/') + "/");
                var imgUri = new Uri(url);
                if (!string.Equals(imgUri.Host, "localhost", StringComparison.OrdinalIgnoreCase) &&
                    imgUri.Host != "127.0.0.1")
                    return url;
                return new UriBuilder(imgUri)
                {
                    Scheme = apiUri.Scheme,
                    Host = apiUri.Host,
                    Port = apiUri.IsDefaultPort ? -1 : apiUri.Port
                }.Uri.ToString();
            }
            catch
            {
                return url;
            }
        }

        void OnDestroy()
        {
            if (_ownedFront != null)
                Destroy(_ownedFront);
            if (_ownedBack != null)
                Destroy(_ownedBack);
        }
    }
}
