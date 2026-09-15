using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class ConceptResultScreen : ScreenBase
    {
        Text _body = null!;
        RawImage _preview = null!;
        Texture2D? _ownedPreview;
        RectTransform _previewHost = null!;

        public override ScreenId Id => ScreenId.ConceptResult;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);

            // Compact top chrome — leave vertical space for a mannequin-sized look
            var top = new GameObject("Top", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var topRt = top.GetComponent<RectTransform>();
            topRt.SetParent(root, false);
            topRt.anchorMin = new Vector2(0f, 1f);
            topRt.anchorMax = new Vector2(1f, 1f);
            topRt.pivot = new Vector2(0.5f, 1f);
            topRt.sizeDelta = new Vector2(0f, 88f);
            var topV = top.GetComponent<VerticalLayoutGroup>();
            topV.padding = new RectOffset(16, 16, 10, 4);
            topV.spacing = 2f;
            topV.childAlignment = TextAnchor.UpperCenter;
            topV.childControlWidth = true;
            topV.childForceExpandWidth = true;
            topV.childControlHeight = true;
            topV.childForceExpandHeight = false;
            FrUiFactory.AddLabel(top.transform, "H", "YOUR LOOK", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.MiddleCenter);
            FrUiFactory.AddLabel(top.transform, "Tag", "exactly what you drew — polished", t,
                Mathf.RoundToInt(t.CaptionSize), FontStyle.Italic, TextAnchor.MiddleCenter, useSecondaryTextColor: true);

            // Full-height stage — same mannequin footprint as the sketch studio
            var stage = new GameObject("LookStage", typeof(RectTransform), typeof(Image));
            stage.transform.SetParent(root, false);
            _previewHost = stage.GetComponent<RectTransform>();
            _previewHost.anchorMin = new Vector2(0f, 0f);
            _previewHost.anchorMax = new Vector2(1f, 1f);
            _previewHost.offsetMin = new Vector2(24f, 168f);
            _previewHost.offsetMax = new Vector2(-24f, -96f);
            var stageImg = stage.GetComponent<Image>();
            stageImg.sprite = FrUiSprites.RoundSoft;
            stageImg.type = Image.Type.Sliced;
            stageImg.color = new Color(1f, 1f, 1f, 0.55f);
            var stageShadow = stage.AddComponent<Shadow>();
            stageShadow.effectColor = new Color(0.2f, 0.08f, 0.14f, 0.16f);
            stageShadow.effectDistance = new Vector2(0f, -8f);

            var glow = new GameObject("Glow", typeof(RectTransform), typeof(Image));
            glow.transform.SetParent(stage.transform, false);
            var glowRt = glow.GetComponent<RectTransform>();
            glowRt.anchorMin = new Vector2(0.15f, 0.02f);
            glowRt.anchorMax = new Vector2(0.85f, 0.98f);
            glowRt.offsetMin = Vector2.zero;
            glowRt.offsetMax = Vector2.zero;
            var glowImg = glow.GetComponent<Image>();
            glowImg.sprite = FrUiSprites.Circle;
            glowImg.color = new Color(t.Champagne.r, t.Champagne.g, t.Champagne.b, 0.4f);
            glowImg.raycastTarget = false;
            glow.AddComponent<FrUiMotion>().EnablePulse(true);

            var previewGo = new GameObject("LookPreview", typeof(RectTransform), typeof(RawImage),
                typeof(AspectRatioFitter));
            previewGo.transform.SetParent(stage.transform, false);
            var previewRt = previewGo.GetComponent<RectTransform>();
            // Match sketch canvas: full stage height, width from aspect
            previewRt.anchorMin = new Vector2(0.5f, 0f);
            previewRt.anchorMax = new Vector2(0.5f, 1f);
            previewRt.pivot = new Vector2(0.5f, 0.5f);
            previewRt.offsetMin = new Vector2(0f, 8f);
            previewRt.offsetMax = new Vector2(0f, -8f);
            _preview = previewGo.GetComponent<RawImage>();
            _preview.color = Color.white;
            _preview.raycastTarget = false;
            _preview.texture = Texture2D.whiteTexture;
            var fitter = previewGo.GetComponent<AspectRatioFitter>();
            fitter.aspectMode = AspectRatioFitter.AspectMode.HeightControlsWidth;
            fitter.aspectRatio = 0.75f; // same as sketch pad 768×1024
            stage.SetActive(false);

            // Bottom actions
            var bottom = new GameObject("Bottom", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var bottomRt = bottom.GetComponent<RectTransform>();
            bottomRt.SetParent(root, false);
            bottomRt.anchorMin = new Vector2(0f, 0f);
            bottomRt.anchorMax = new Vector2(1f, 0f);
            bottomRt.pivot = new Vector2(0.5f, 0f);
            bottomRt.sizeDelta = new Vector2(0f, 160f);
            var bottomV = bottom.GetComponent<VerticalLayoutGroup>();
            bottomV.padding = new RectOffset(20, 20, 6, 14);
            bottomV.spacing = 8f;
            bottomV.childAlignment = TextAnchor.LowerCenter;
            bottomV.childControlWidth = true;
            bottomV.childForceExpandWidth = true;
            bottomV.childControlHeight = true;
            bottomV.childForceExpandHeight = false;

            _body = FrUiFactory.AddLabel(bottom.transform, "B", "", t, Mathf.RoundToInt(t.CaptionSize),
                FontStyle.Normal, TextAnchor.MiddleCenter, useSecondaryTextColor: true);
            var bodyLe = _body.GetComponent<LayoutElement>() ?? _body.gameObject.AddComponent<LayoutElement>();
            bodyLe.minHeight = 28f;
            bodyLe.preferredHeight = 32f;

            FrUiFactory.AddButton(bottom.transform, "SHARE!", t, ShareLook, FrButtonEmphasis.Primary);

            var row = new GameObject("NavRow", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            row.transform.SetParent(bottom.transform, false);
            var rowLe = row.GetComponent<LayoutElement>();
            rowLe.minHeight = 52f;
            rowLe.preferredHeight = 52f;
            rowLe.flexibleWidth = 1f;
            var rowH = row.GetComponent<HorizontalLayoutGroup>();
            rowH.spacing = 10f;
            rowH.childAlignment = TextAnchor.MiddleCenter;
            rowH.childControlWidth = true;
            rowH.childForceExpandWidth = true;
            rowH.childControlHeight = true;
            rowH.childForceExpandHeight = true;
            FrUiFactory.AddButton(row.transform, "Draw again", t, DrawAgain);
            FrUiFactory.AddButton(row.transform, "Home", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.HomeDashboard);
            });
        }

        void OnDestroy() => ClearPreviewTexture();

        void DrawAgain()
        {
            App.CreateDesign.ClearLastLook();
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.HomeDashboard);
        }

        public override async Task ShowAsync(object? payload = null, CancellationToken cancellationToken = default)
        {
            gameObject.SetActive(true);
            ClearPreviewTexture();
            SetPreviewVisible(false);

            var sb = new StringBuilder();
            sb.Append("You made this!");
            var summary = App.CreateDesign.LastSketchSummary?.Trim() ?? "";
            if (!string.IsNullOrEmpty(summary))
            {
                var firstLine = summary.Split('\n')[0].Trim();
                if (firstLine.Length > 90)
                    firstLine = firstLine.Substring(0, 87) + "…";
                if (!string.IsNullOrEmpty(firstLine) &&
                    !firstLine.StartsWith("Source:", StringComparison.OrdinalIgnoreCase) &&
                    !firstLine.StartsWith("Model:", StringComparison.OrdinalIgnoreCase))
                    sb.Append(' ').Append(firstLine);
            }

            _body.text = sb.ToString();

            var imageUrl = App.CreateDesign.LastPolishedImageUrl?.Trim() ?? "";

            if (App.IsApiBackend && App.Auth.HasBackendSession &&
                !string.IsNullOrWhiteSpace(App.CreateDesign.LastSketchJobId))
            {
                try
                {
                    var fromJob = await App.Ai
                        .GetJobImageUrlAsync(App.CreateDesign.LastSketchJobId, cancellationToken)
                        .ConfigureAwait(true);
                    if (!string.IsNullOrEmpty(fromJob))
                    {
                        imageUrl = fromJob!;
                        App.CreateDesign.LastPolishedImageUrl = imageUrl;
                    }

                    var detail = await App.Ai
                        .GetJobStructuredDetailTextAsync(App.CreateDesign.LastSketchJobId, cancellationToken)
                        .ConfigureAwait(true);
                    if (!string.IsNullOrEmpty(detail))
                        Debug.Log($"FashionRise look detail:\n{detail}");
                }
                catch (Exception ex)
                {
                    Debug.LogWarning($"FashionRise Could not load job details: {ex.Message}");
                }
            }

            if (!string.IsNullOrEmpty(imageUrl))
            {
                var loadUrl = RewriteUploadUrlToApiHost(imageUrl);
                _body.text = "Loading your look…";
                Debug.Log($"FashionRise ConceptResult loading look: {loadUrl}");
                try
                {
                    var err = await LoadPolishedPreviewAsync(loadUrl, cancellationToken).ConfigureAwait(true);
                    if (IsPreviewVisible())
                        _body.text = sb.ToString();
                    else
                        _body.text = sb +
                                     $"  (Could not show the image{(string.IsNullOrEmpty(err) ? "" : ": " + err)})";
                }
                catch (Exception ex)
                {
                    _body.text = sb + $"  (Image load: {ex.Message})";
                    TryShowLocalSketchFallback();
                }
            }
            else
            {
                TryShowLocalSketchFallback();
            }
        }

        void TryShowLocalSketchFallback()
        {
            var sketchPath = ResolveLocalSketchPath();
            if (!string.IsNullOrEmpty(sketchPath))
                TryShowLocalFile(sketchPath!);
        }

        string RewriteUploadUrlToApiHost(string url)
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

                var b = new UriBuilder(imgUri)
                {
                    Scheme = apiUri.Scheme,
                    Host = apiUri.Host,
                    Port = apiUri.IsDefaultPort ? -1 : apiUri.Port
                };
                return b.Uri.ToString();
            }
            catch
            {
                return url;
            }
        }

        async Task<string?> LoadPolishedPreviewAsync(string url, CancellationToken cancellationToken)
        {
            using var req = UnityWebRequestTexture.GetTexture(url);
            var op = req.SendWebRequest();
            while (!op.isDone)
                await Task.Delay(32, cancellationToken).ConfigureAwait(true);

            cancellationToken.ThrowIfCancellationRequested();
            if (req.result != UnityWebRequest.Result.Success)
            {
                Debug.LogWarning($"FashionRise look image download failed: {req.error} ({url})");
                return req.error ?? "download failed";
            }

            var tex = DownloadHandlerTexture.GetContent(req);
            if (tex == null)
                return "empty texture";

            ClearPreviewTexture();
            _ownedPreview = tex;
            _preview.texture = tex;
            ApplyPreviewAspect(tex);
            SetPreviewVisible(true);
            try
            {
                var dir = Path.Combine(UnityEngine.Application.persistentDataPath, "Looks");
                Directory.CreateDirectory(dir);
                var path = Path.Combine(dir, $"look_{DateTime.UtcNow:yyyyMMdd_HHmmssfff}.png");
                File.WriteAllBytes(path, tex.EncodeToPNG());
                App.CreateDesign.LastPolishedImageLocalPath = path;
            }
            catch
            {
                /* share can still use URL download path later */
            }

            return null;
        }

        void TryShowLocalFile(string path)
        {
            try
            {
                var bytes = File.ReadAllBytes(path);
                var tex = new Texture2D(2, 2, TextureFormat.RGBA32, false);
                if (!tex.LoadImage(bytes))
                {
                    Destroy(tex);
                    return;
                }

                ClearPreviewTexture();
                _ownedPreview = tex;
                _preview.texture = tex;
                ApplyPreviewAspect(tex);
                SetPreviewVisible(true);
            }
            catch
            {
                /* ignore */
            }
        }

        void ApplyPreviewAspect(Texture tex)
        {
            var fitter = _preview.GetComponent<AspectRatioFitter>();
            if (fitter == null || tex == null || tex.height <= 0)
                return;
            // Prefer mannequin-matching portrait; if the look is wider, still fill height when possible.
            var aspect = tex.width / (float)tex.height;
            fitter.aspectMode = AspectRatioFitter.AspectMode.HeightControlsWidth;
            fitter.aspectRatio = aspect > 0.05f ? aspect : 0.75f;
        }

        void SetPreviewVisible(bool visible)
        {
            if (_previewHost != null)
                _previewHost.gameObject.SetActive(visible);
            if (_preview != null)
                _preview.gameObject.SetActive(visible);
        }

        bool IsPreviewVisible() =>
            _preview != null && _preview.gameObject.activeInHierarchy;

        void ClearPreviewTexture()
        {
            if (_ownedPreview != null)
            {
                Destroy(_ownedPreview);
                _ownedPreview = null;
            }

            if (_preview != null)
                _preview.texture = Texture2D.whiteTexture;
        }

        void ShareLook()
        {
            const string caption = "I made this on FashionRise!";
            var path = App.CreateDesign.LastPolishedImageLocalPath?.Trim();
            if (string.IsNullOrEmpty(path) || !File.Exists(path))
                path = ResolveLocalSketchPath();

            if (!string.IsNullOrEmpty(path) &&
                NativeShareSheet.TryShareImageFile(path, caption, "FashionRise look"))
            {
                _body.text += "  (Share opened.)";
                return;
            }

            if (NativeShareSheet.TryShareText(caption, "FashionRise look"))
            {
                _body.text += "  (Share opened.)";
                return;
            }

            ShareClipboard.Copy(caption + (string.IsNullOrEmpty(path) ? "" : "\n" + path));
            _body.text += "  (Copied — paste to share.)";
        }

        string? ResolveLocalSketchPath()
        {
            var raw = App.CreateDesign.SketchReference?.Trim();
            if (string.IsNullOrEmpty(raw))
                return null;
            if (raw.StartsWith("file:", StringComparison.OrdinalIgnoreCase))
                raw = raw.Substring(5);
            raw = raw.Replace('/', Path.DirectorySeparatorChar);
            return File.Exists(raw) ? raw : null;
        }
    }
}
