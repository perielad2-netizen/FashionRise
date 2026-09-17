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

            // Slim title strip
            var top = new GameObject("Top", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var topRt = top.GetComponent<RectTransform>();
            topRt.SetParent(root, false);
            topRt.anchorMin = new Vector2(0f, 1f);
            topRt.anchorMax = new Vector2(1f, 1f);
            topRt.pivot = new Vector2(0.5f, 1f);
            topRt.sizeDelta = new Vector2(0f, 56f);
            var topV = top.GetComponent<VerticalLayoutGroup>();
            topV.padding = new RectOffset(12, 12, 8, 2);
            topV.spacing = 0f;
            topV.childAlignment = TextAnchor.MiddleCenter;
            topV.childControlWidth = true;
            topV.childForceExpandWidth = true;
            topV.childControlHeight = true;
            topV.childForceExpandHeight = false;
            FrUiFactory.AddLabel(top.transform, "H", "YOUR LOOK", t, Mathf.RoundToInt(t.SubtitleSize + 4f),
                FontStyle.Bold, TextAnchor.MiddleCenter);

            // Compact bottom bar — SHARE + Edit + Draw again / Home must all fit on iPad Mini
            const float bottomH = 168f;
            var bottom = new GameObject("Bottom", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var bottomRt = bottom.GetComponent<RectTransform>();
            bottomRt.SetParent(root, false);
            bottomRt.anchorMin = new Vector2(0f, 0f);
            bottomRt.anchorMax = new Vector2(1f, 0f);
            bottomRt.pivot = new Vector2(0.5f, 0f);
            bottomRt.sizeDelta = new Vector2(0f, bottomH);
            var bottomV = bottom.GetComponent<VerticalLayoutGroup>();
            bottomV.padding = new RectOffset(14, 14, 4, 10);
            bottomV.spacing = 6f;
            bottomV.childAlignment = TextAnchor.LowerCenter;
            bottomV.childControlWidth = true;
            bottomV.childForceExpandWidth = true;
            bottomV.childControlHeight = true;
            bottomV.childForceExpandHeight = false;

            _body = FrUiFactory.AddLabel(bottom.transform, "B", "", t, Mathf.RoundToInt(t.CaptionSize),
                FontStyle.Normal, TextAnchor.MiddleCenter, useSecondaryTextColor: true);
            var bodyLe = _body.GetComponent<LayoutElement>() ?? _body.gameObject.AddComponent<LayoutElement>();
            bodyLe.minHeight = 18f;
            bodyLe.preferredHeight = 20f;
            bodyLe.flexibleHeight = 0f;

            var share = FrUiFactory.AddButton(bottom.transform, "SHARE!", t, ShareLook, FrButtonEmphasis.Primary);
            ShrinkAction(share, 48f);

            var row = new GameObject("Actions", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            row.transform.SetParent(bottom.transform, false);
            var rowLe = row.GetComponent<LayoutElement>();
            rowLe.minHeight = 46f;
            rowLe.preferredHeight = 46f;
            rowLe.flexibleWidth = 1f;
            var rowH = row.GetComponent<HorizontalLayoutGroup>();
            rowH.spacing = 8f;
            rowH.childAlignment = TextAnchor.MiddleCenter;
            rowH.childControlWidth = true;
            rowH.childForceExpandWidth = true;
            rowH.childControlHeight = true;
            rowH.childForceExpandHeight = true;

            var edit = FrUiFactory.AddButton(row.transform, "Edit sketch", t, EditSketch);
            ShrinkAction(edit, 46f);
            var draw = FrUiFactory.AddButton(row.transform, "Draw again", t, DrawAgain);
            ShrinkAction(draw, 46f);
            var home = FrUiFactory.AddButton(row.transform, "Home", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.HomeDashboard);
            });
            ShrinkAction(home, 46f);

            // Look stage fills everything between title and bottom bar
            var stage = new GameObject("LookStage", typeof(RectTransform), typeof(Image));
            stage.transform.SetParent(root, false);
            _previewHost = stage.GetComponent<RectTransform>();
            _previewHost.anchorMin = new Vector2(0f, 0f);
            _previewHost.anchorMax = new Vector2(1f, 1f);
            _previewHost.offsetMin = new Vector2(16f, bottomH + 4f);
            _previewHost.offsetMax = new Vector2(-16f, -58f);
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
            glowRt.anchorMin = new Vector2(0.12f, 0.02f);
            glowRt.anchorMax = new Vector2(0.88f, 0.98f);
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
            previewRt.anchorMin = new Vector2(0.5f, 0f);
            previewRt.anchorMax = new Vector2(0.5f, 1f);
            previewRt.pivot = new Vector2(0.5f, 0.5f);
            previewRt.offsetMin = new Vector2(0f, 6f);
            previewRt.offsetMax = new Vector2(0f, -6f);
            _preview = previewGo.GetComponent<RawImage>();
            _preview.color = Color.white;
            _preview.raycastTarget = false;
            _preview.texture = Texture2D.whiteTexture;
            var fitter = previewGo.GetComponent<AspectRatioFitter>();
            fitter.aspectMode = AspectRatioFitter.AspectMode.HeightControlsWidth;
            fitter.aspectRatio = 0.75f;
            stage.SetActive(false);
        }

        static void ShrinkAction(Button btn, float height)
        {
            var le = btn.GetComponent<LayoutElement>();
            if (le == null)
                return;
            le.minHeight = height;
            le.preferredHeight = height;
            le.flexibleHeight = 0f;
        }

        void OnDestroy() => ClearPreviewTexture();

        void EditSketch()
        {
            App.CreateDesign.ClearLastLook();
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.SketchCanvas,
                    new SketchNavContext { RestoreSketch = true });
        }

        void DrawAgain()
        {
            App.CreateDesign.ClearLastLook();
            App.CreateDesign.LastInkImagePath = "";
            App.CreateDesign.SketchMaterialPairs = "";
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
                if (firstLine.Length > 70)
                    firstLine = firstLine.Substring(0, 67) + "…";
                if (!string.IsNullOrEmpty(firstLine) &&
                    !firstLine.StartsWith("Source:", StringComparison.OrdinalIgnoreCase) &&
                    !firstLine.StartsWith("Model:", StringComparison.OrdinalIgnoreCase) &&
                    !firstLine.StartsWith("Transform", StringComparison.OrdinalIgnoreCase))
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
                                     $"  (Could not show{(string.IsNullOrEmpty(err) ? "" : ": " + err)})";
                }
                catch (Exception ex)
                {
                    _body.text = sb + $"  (Image: {ex.Message})";
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
                /* share can still use URL later */
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
