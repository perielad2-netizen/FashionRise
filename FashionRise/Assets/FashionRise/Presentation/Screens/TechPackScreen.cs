using System;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Core.Navigation;
using FashionRise.UI;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>
    /// Professional Technical Design / Tech Pack — Design View, Measurements, Pattern, Materials, Construction.
    /// Measurements are a first production draft and remain editable later.
    /// </summary>
    public sealed class TechPackScreen : ScreenBase
    {
        Text _title = null!;
        Text _body = null!;
        Text _disclaimer = null!;
        RawImage _front = null!;
        RawImage _back = null!;
        Texture2D? _ownedFront;
        Texture2D? _ownedBack;
        FrAiLoadingFx? _loading;
        string _activeSection = "design";

        public override ScreenId Id => ScreenId.TechPack;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            _loading = FrAiLoadingFx.Create(root, t);

            var top = new GameObject("Top", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var topRt = top.GetComponent<RectTransform>();
            topRt.SetParent(root, false);
            topRt.anchorMin = new Vector2(0f, 1f);
            topRt.anchorMax = new Vector2(1f, 1f);
            topRt.pivot = new Vector2(0.5f, 1f);
            topRt.sizeDelta = new Vector2(0f, 92f);
            var topV = top.GetComponent<VerticalLayoutGroup>();
            topV.padding = new RectOffset(24, 24, 16, 8);
            topV.spacing = 2f;
            topV.childAlignment = TextAnchor.UpperCenter;
            topV.childControlWidth = true;
            topV.childForceExpandWidth = true;
            FrUiFactory.AddOverline(top.transform, "Ov", "Fashion technical specification", t);
            _title = FrUiFactory.AddEditorialLabel(top.transform, "H", "Tech Pack", t,
                Mathf.RoundToInt(t.TitleSize), true, TextAnchor.MiddleCenter);

            var tabs = new GameObject("Tabs", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            var tabsRt = tabs.GetComponent<RectTransform>();
            tabsRt.SetParent(root, false);
            tabsRt.anchorMin = new Vector2(0f, 1f);
            tabsRt.anchorMax = new Vector2(1f, 1f);
            tabsRt.pivot = new Vector2(0.5f, 1f);
            tabsRt.anchoredPosition = new Vector2(0f, -96f);
            tabsRt.sizeDelta = new Vector2(0f, 44f);
            var tabsH = tabs.GetComponent<HorizontalLayoutGroup>();
            tabsH.padding = new RectOffset(12, 12, 0, 0);
            tabsH.spacing = 6f;
            tabsH.childForceExpandWidth = true;
            tabsH.childControlWidth = true;
            tabsH.childControlHeight = true;
            AddTab(tabs.transform, "Design", "design", t);
            AddTab(tabs.transform, "Measure", "measurements", t);
            AddTab(tabs.transform, "Pattern", "pattern", t);
            AddTab(tabs.transform, "Materials", "materials", t);
            AddTab(tabs.transform, "Build", "construction", t);

            const float bottomH = 120f;
            var bottom = new GameObject("Bottom", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var bottomRt = bottom.GetComponent<RectTransform>();
            bottomRt.SetParent(root, false);
            bottomRt.anchorMin = new Vector2(0f, 0f);
            bottomRt.anchorMax = new Vector2(1f, 0f);
            bottomRt.pivot = new Vector2(0.5f, 0f);
            bottomRt.sizeDelta = new Vector2(0f, bottomH);
            var bottomV = bottom.GetComponent<VerticalLayoutGroup>();
            bottomV.padding = new RectOffset(20, 20, 6, 14);
            bottomV.spacing = 6f;
            bottomV.childControlWidth = true;
            bottomV.childForceExpandWidth = true;
            _disclaimer = FrUiFactory.AddLabel(bottom.transform, "Disc", "", t,
                Mathf.RoundToInt(t.CaptionSize), FontStyle.Normal, TextAnchor.MiddleCenter, true);
            var row = FrUiFactory.AddHorizontalRow(bottom.transform, "Nav", 8f);
            row.GetComponent<LayoutElement>().minHeight = 48f;
            row.GetComponent<LayoutElement>().preferredHeight = 48f;
            FrUiFactory.AddButton(row, "Back to look", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.ConceptResult);
            });
            FrUiFactory.AddButton(row, "Home", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.HomeDashboard);
            }, FrButtonEmphasis.Ghost);

            var scrollGo = new GameObject("Scroll", typeof(RectTransform), typeof(ScrollRect), typeof(Image));
            var scrollRt = scrollGo.GetComponent<RectTransform>();
            scrollRt.SetParent(root, false);
            scrollRt.anchorMin = Vector2.zero;
            scrollRt.anchorMax = Vector2.one;
            scrollRt.offsetMin = new Vector2(16f, bottomH + 4f);
            scrollRt.offsetMax = new Vector2(-16f, -148f);
            scrollGo.GetComponent<Image>().color = new Color(1f, 1f, 1f, 0.25f);
            var scroll = scrollGo.GetComponent<ScrollRect>();
            scroll.horizontal = false;
            scroll.movementType = ScrollRect.MovementType.Clamped;

            var content = new GameObject("Content", typeof(RectTransform), typeof(VerticalLayoutGroup),
                typeof(ContentSizeFitter));
            var contentRt = content.GetComponent<RectTransform>();
            contentRt.SetParent(scrollRt, false);
            contentRt.anchorMin = new Vector2(0f, 1f);
            contentRt.anchorMax = new Vector2(1f, 1f);
            contentRt.pivot = new Vector2(0.5f, 1f);
            contentRt.sizeDelta = new Vector2(0f, 0f);
            var cv = content.GetComponent<VerticalLayoutGroup>();
            cv.padding = new RectOffset(12, 12, 12, 24);
            cv.spacing = 14f;
            cv.childControlWidth = true;
            cv.childForceExpandWidth = true;
            cv.childControlHeight = true;
            cv.childForceExpandHeight = false;
            content.GetComponent<ContentSizeFitter>().verticalFit = ContentSizeFitter.FitMode.PreferredSize;
            scroll.content = contentRt;
            scroll.viewport = scrollRt;

            var flats = new GameObject("Flats", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            flats.transform.SetParent(content.transform, false);
            var flatsLe = flats.GetComponent<LayoutElement>();
            flatsLe.minHeight = 280f;
            flatsLe.preferredHeight = 320f;
            var flatsH = flats.GetComponent<HorizontalLayoutGroup>();
            flatsH.spacing = 12f;
            flatsH.childForceExpandWidth = true;
            flatsH.childControlWidth = true;
            flatsH.childControlHeight = true;
            _front = MakeFlat(flats.transform, "Front", t);
            _back = MakeFlat(flats.transform, "Back", t);

            _body = FrUiFactory.AddLabel(content.transform, "Body", "", t, Mathf.RoundToInt(t.BodySize),
                FontStyle.Normal, TextAnchor.UpperLeft);
            _body.horizontalOverflow = HorizontalWrapMode.Wrap;
            _body.verticalOverflow = VerticalWrapMode.Overflow;
            var bodyLe = _body.GetComponent<LayoutElement>();
            bodyLe.minHeight = 400f;
            bodyLe.preferredHeight = 800f;
            bodyLe.flexibleHeight = 1f;
        }

        void AddTab(Transform parent, string label, string key, FashionRise.Content.FashionRiseTheme t)
        {
            FrUiFactory.AddButton(parent, label, t, () =>
            {
                _activeSection = key;
                RenderSection();
            }, FrButtonEmphasis.Ghost);
        }

        static RawImage MakeFlat(Transform parent, string label, FashionRise.Content.FashionRiseTheme t)
        {
            var go = new GameObject(label, typeof(RectTransform), typeof(Image), typeof(LayoutElement));
            go.transform.SetParent(parent, false);
            go.GetComponent<Image>().color = t.Card;
            var le = go.GetComponent<LayoutElement>();
            le.flexibleWidth = 1f;
            FrUiFactory.AddLabel(go.transform, "L", label.ToUpperInvariant() + " VIEW", t,
                Mathf.RoundToInt(t.CaptionSize), FontStyle.Normal, TextAnchor.UpperCenter, true);
            var imgGo = new GameObject("Img", typeof(RectTransform), typeof(RawImage));
            var rt = imgGo.GetComponent<RectTransform>();
            rt.SetParent(go.transform, false);
            rt.anchorMin = new Vector2(0.06f, 0.08f);
            rt.anchorMax = new Vector2(0.94f, 0.88f);
            rt.offsetMin = Vector2.zero;
            rt.offsetMax = Vector2.zero;
            var raw = imgGo.GetComponent<RawImage>();
            raw.texture = Texture2D.whiteTexture;
            raw.color = new Color(1f, 1f, 1f, 0.9f);
            return raw;
        }

        public override async Task ShowAsync(object? payload = null, CancellationToken cancellationToken = default)
        {
            gameObject.SetActive(true);
            _activeSection = "design";
            if (string.IsNullOrWhiteSpace(App.CreateDesign.LastTechPackJson))
                await GenerateAsync(cancellationToken).ConfigureAwait(true);
            else
                RenderSection();
            await LoadFlatImagesAsync(cancellationToken).ConfigureAwait(true);
        }

        async Task GenerateAsync(CancellationToken cancellationToken)
        {
            _loading?.Show("Extracting pattern & construction…");
            try
            {
                var sketch = App.CreateDesign.LastInkImagePath;
                if (string.IsNullOrEmpty(sketch))
                {
                    var raw = App.CreateDesign.SketchReference?.Trim() ?? "";
                    if (raw.StartsWith("file:", StringComparison.OrdinalIgnoreCase))
                        sketch = raw.Substring(5);
                    else
                        sketch = raw;
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
                    OnJobStarted = id => App.CreateDesign.LastTechPackJobId = id
                }, cancellationToken).ConfigureAwait(true);

                App.CreateDesign.LastTechPackJobId = result.JobId;
                App.CreateDesign.LastTechPackJson = result.RawJson;
                App.CreateDesign.LastTechPackFrontImageUrl = result.FrontImageUrl;
                App.CreateDesign.LastTechPackBackImageUrl = result.BackImageUrl;
                App.CreateDesign.LastTechPackPatternImageUrl = result.PatternImageUrl;
                _title.text = "Tech Pack";
                RenderSection();
            }
            catch (Exception ex)
            {
                _body.text = "Could not build tech pack: " + ex.Message;
                _disclaimer.text = "Draft measurements — not final manufacturing specs.";
            }
            finally
            {
                _loading?.Hide();
            }
        }

        void RenderSection()
        {
            var json = App.CreateDesign.LastTechPackJson;
            if (string.IsNullOrWhiteSpace(json))
            {
                _body.text = "No tech pack yet.";
                return;
            }

            try
            {
                var root = JObject.Parse(json);
                _disclaimer.text = root.Value<string>("disclaimer")
                                   ?? "Draft measurements — not final manufacturing specs.";
                var garment = root["garment"] as JObject;
                var gType = garment?.Value<string>("type") ?? "Garment";
                _title.text = gType;

                var sb = new StringBuilder();
                switch (_activeSection)
                {
                    case "measurements":
                        sb.AppendLine("SAMPLE SIZE");
                        var m = root["measurements"] as JObject;
                        sb.AppendLine(m?.Value<string>("sample_size") ?? "EU 36 / US 4");
                        sb.AppendLine();
                        sb.AppendLine("BODY (baseline)");
                        AppendObject(sb, m?["body"] as JObject);
                        sb.AppendLine();
                        sb.AppendLine("FINISHED GARMENT");
                        AppendObject(sb, m?["finished"] as JObject);
                        sb.AppendLine();
                        sb.AppendLine("Editable later — treat as first production draft.");
                        break;
                    case "pattern":
                        sb.AppendLine("PATTERN PIECES");
                        if (root["pattern_pieces"] is JArray pieces)
                            foreach (var p in pieces)
                            {
                                sb.Append("• ").Append(p.Value<string>("name") ?? "Piece");
                                var w = p.Value<float?>("width_cm");
                                var h = p.Value<float?>("height_cm");
                                if (w != null && h != null)
                                    sb.Append($"  {w:0.#} × {h:0.#} cm");
                                var sa = p.Value<float?>("seam_allowance_cm");
                                if (sa != null)
                                    sb.Append($"  SA {sa:0.#} cm");
                                sb.AppendLine();
                            }

                        sb.AppendLine();
                        sb.AppendLine("CUTTING LAYOUT");
                        AppendObject(sb, root["cutting_layout"] as JObject);
                        break;
                    case "materials":
                        sb.AppendLine("MATERIALS & NOTIONS");
                        if (root["materials"] is JArray mats)
                            foreach (var mat in mats)
                            {
                                sb.Append("• ").Append(mat.Value<string>("name") ?? "Item");
                                var role = mat.Value<string>("role");
                                if (!string.IsNullOrEmpty(role))
                                    sb.Append($"  ({role})");
                                var qty = mat.Value<float?>("quantity_m");
                                if (qty != null)
                                    sb.Append($"  — {qty:0.##} m");
                                sb.AppendLine();
                                var rec = mat.Value<string>("recommendation") ?? mat.Value<string>("notes");
                                if (!string.IsNullOrEmpty(rec))
                                    sb.Append("    ").AppendLine(rec);
                            }

                        break;
                    case "construction":
                        sb.AppendLine("CONSTRUCTION STEPS");
                        if (root["construction_steps"] is JArray steps)
                        {
                            var i = 1;
                            foreach (var s in steps)
                                sb.Append(i++).Append(". ").AppendLine(s.ToString());
                        }

                        break;
                    default:
                        sb.AppendLine("DESIGN VIEW");
                        sb.AppendLine(root.Value<string>("summary") ?? "");
                        sb.AppendLine();
                        if (garment != null)
                        {
                            sb.AppendLine(garment.Value<string>("construction_description") ?? "");
                            sb.AppendLine();
                            AppendObject(sb, garment);
                        }

                        break;
                }

                _body.text = sb.ToString();
                var preferred = Mathf.Max(400f, 22f * (_body.text.Split('\n').Length + 4));
                var le = _body.GetComponent<LayoutElement>();
                le.minHeight = preferred;
                le.preferredHeight = preferred;
            }
            catch (Exception ex)
            {
                _body.text = "Could not parse tech pack.\n" + ex.Message + "\n\n" + json;
            }
        }

        static void AppendObject(StringBuilder sb, JObject? obj)
        {
            if (obj == null)
                return;
            foreach (var p in obj.Properties())
            {
                if (p.Name is "type" or "construction_description")
                    continue;
                sb.Append(p.Name.Replace('_', ' ')).Append(": ").AppendLine(p.Value?.ToString() ?? "");
            }
        }

        async Task LoadFlatImagesAsync(CancellationToken cancellationToken)
        {
            await LoadOneAsync(_front, ref _ownedFront, App.CreateDesign.LastTechPackFrontImageUrl, cancellationToken)
                .ConfigureAwait(true);
            await LoadOneAsync(_back, ref _ownedBack, App.CreateDesign.LastTechPackBackImageUrl, cancellationToken)
                .ConfigureAwait(true);
        }

        async Task LoadOneAsync(RawImage target, ref Texture2D? owned, string url, CancellationToken ct)
        {
            if (string.IsNullOrWhiteSpace(url) || target == null)
                return;
            try
            {
                using var req = UnityWebRequestTexture.GetTexture(url);
                var op = req.SendWebRequest();
                while (!op.isDone)
                    await Task.Delay(32, ct).ConfigureAwait(true);
                if (req.result != UnityWebRequest.Result.Success)
                    return;
                var tex = DownloadHandlerTexture.GetContent(req);
                if (tex == null)
                    return;
                if (owned != null)
                    Destroy(owned);
                owned = tex;
                target.texture = tex;
            }
            catch
            {
                /* optional visuals */
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
