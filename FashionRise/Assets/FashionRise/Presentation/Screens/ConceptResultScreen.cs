using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Core.Navigation;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>Shows the Magic look image (and summary) after sketch polish.</summary>
    public sealed class ConceptResultScreen : ScreenBase
    {
        Text _body = null!;
        RawImage _preview = null!;
        Texture2D? _ownedPreview;

        public override ScreenId Id => ScreenId.ConceptResult;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Your look", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);

            var previewHost = new GameObject("LookPreviewHost", typeof(RectTransform), typeof(LayoutElement));
            previewHost.transform.SetParent(col, false);
            var hostLe = previewHost.GetComponent<LayoutElement>();
            hostLe.minHeight = 280f;
            hostLe.preferredHeight = 480f;
            hostLe.flexibleWidth = 1f;

            var previewGo = new GameObject("LookPreview", typeof(RectTransform), typeof(RawImage),
                typeof(AspectRatioFitter));
            previewGo.transform.SetParent(previewHost.transform, false);
            var previewRt = previewGo.GetComponent<RectTransform>();
            previewRt.anchorMin = new Vector2(0.5f, 0.5f);
            previewRt.anchorMax = new Vector2(0.5f, 0.5f);
            previewRt.pivot = new Vector2(0.5f, 0.5f);
            previewRt.sizeDelta = new Vector2(360f, 480f);
            _preview = previewGo.GetComponent<RawImage>();
            _preview.color = Color.white;
            _preview.raycastTarget = false;
            _preview.texture = Texture2D.whiteTexture;
            var fitter = previewGo.GetComponent<AspectRatioFitter>();
            fitter.aspectMode = AspectRatioFitter.AspectMode.FitInParent;
            fitter.aspectRatio = 0.75f;
            previewHost.SetActive(false);

            _body = FrUiFactory.AddLabel(col, "B", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperLeft);
            var bodyLe = _body.gameObject.AddComponent<LayoutElement>();
            bodyLe.minHeight = 72f;
            bodyLe.preferredHeight = 140f;

            FrUiFactory.AddButton(col, "Share!", t, ShareLook);
            FrUiFactory.AddButton(col, "Draw again", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.HomeDashboard);
            });
            FrUiFactory.AddButton(col, "Try more magic", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.SketchEnhancement);
            });
            FrUiFactory.AddButton(col, "Home", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.HomeDashboard);
            });
        }

        void OnDestroy() => ClearPreviewTexture();

        public override async Task ShowAsync(object? payload = null, CancellationToken cancellationToken = default)
        {
            gameObject.SetActive(true);
            ClearPreviewTexture();
            SetPreviewVisible(false);

            var sb = new StringBuilder();
            sb.AppendLine("Magic finished!");
            if (!string.IsNullOrWhiteSpace(App.CreateDesign.LastSketchSummary))
                sb.AppendLine(App.CreateDesign.LastSketchSummary);
            sb.AppendLine();
            sb.AppendLine("Share your look, or draw another one.");
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
                    {
                        sb.AppendLine();
                        sb.AppendLine(detail);
                        _body.text = sb.ToString();
                    }
                }
                catch (Exception ex)
                {
                    _body.text = sb + $"\n\n(Could not load job details: {ex.Message})";
                }
            }

            if (!string.IsNullOrEmpty(imageUrl))
            {
                var loadUrl = RewriteUploadUrlToApiHost(imageUrl);
                _body.text = sb + "\nLoading your AI look…";
                Debug.Log($"FashionRise ConceptResult loading look: {loadUrl}");
                try
                {
                    var err = await LoadPolishedPreviewAsync(loadUrl, cancellationToken).ConfigureAwait(true);
                    if (IsPreviewVisible())
                        _body.text = sb.ToString();
                    else
                        _body.text = sb +
                                     $"\n(Could not show the AI image{(string.IsNullOrEmpty(err) ? "" : ": " + err)} — open the URL in a browser, or Share your sketch.)";
                }
                catch (Exception ex)
                {
                    _body.text = sb + $"\n(Image load: {ex.Message})";
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
            var fitter = _preview.GetComponent<AspectRatioFitter>();
            if (fitter != null && tex.height > 0)
                fitter.aspectRatio = tex.width / (float)tex.height;
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
                /* share can still use sketch fallback */
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
                var fitter = _preview.GetComponent<AspectRatioFitter>();
                if (fitter != null && tex.height > 0)
                    fitter.aspectRatio = tex.width / (float)tex.height;
                SetPreviewVisible(true);
            }
            catch
            {
                /* ignore */
            }
        }

        void SetPreviewVisible(bool visible)
        {
            if (_preview == null)
                return;
            if (_preview.transform.parent != null)
                _preview.transform.parent.gameObject.SetActive(visible);
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

            if (!string.IsNullOrEmpty(path) && File.Exists(path))
            {
                GUIUtility.systemCopyBuffer = caption + "\n" + path;
                _body.text += "\n\n(Look path copied — paste into Messages / WhatsApp.)";
                return;
            }

            GUIUtility.systemCopyBuffer = caption;
            _body.text += "\n\n(Copied caption to clipboard.)";
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
