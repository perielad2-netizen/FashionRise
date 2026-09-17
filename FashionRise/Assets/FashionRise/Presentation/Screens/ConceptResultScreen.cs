using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Core;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>
    /// Your Look — Share, Magic again, or Create Real Design (tech pack).
    /// </summary>
    public sealed class ConceptResultScreen : ScreenBase
    {
        Text _body = null!;
        RawImage _preview = null!;
        Texture2D? _ownedPreview;
        RectTransform _previewHost = null!;
        FrAiLoadingFx? _loading;

        public override ScreenId Id => ScreenId.ConceptResult;

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
            topRt.sizeDelta = new Vector2(0f, 72f);
            var topV = top.GetComponent<VerticalLayoutGroup>();
            topV.padding = new RectOffset(20, 20, 14, 4);
            topV.spacing = 0f;
            topV.childAlignment = TextAnchor.MiddleCenter;
            topV.childControlWidth = true;
            topV.childForceExpandWidth = true;
            FrUiFactory.AddOverline(top.transform, "Ov", "Your collection", t);
            FrUiFactory.AddEditorialLabel(top.transform, "H", "Your Look", t,
                Mathf.RoundToInt(t.TitleSize), true, TextAnchor.MiddleCenter);

            const float bottomH = 210f;
            var bottom = new GameObject("Bottom", typeof(RectTransform), typeof(VerticalLayoutGroup));
            var bottomRt = bottom.GetComponent<RectTransform>();
            bottomRt.SetParent(root, false);
            bottomRt.anchorMin = new Vector2(0f, 0f);
            bottomRt.anchorMax = new Vector2(1f, 0f);
            bottomRt.pivot = new Vector2(0.5f, 0f);
            bottomRt.sizeDelta = new Vector2(0f, bottomH);
            var bottomV = bottom.GetComponent<VerticalLayoutGroup>();
            bottomV.padding = new RectOffset(18, 18, 6, 14);
            bottomV.spacing = 8f;
            bottomV.childAlignment = TextAnchor.LowerCenter;
            bottomV.childControlWidth = true;
            bottomV.childForceExpandWidth = true;
            bottomV.childControlHeight = true;
            bottomV.childForceExpandHeight = false;

            _body = FrUiFactory.AddLabel(bottom.transform, "B", "", t, Mathf.RoundToInt(t.CaptionSize),
                FontStyle.Normal, TextAnchor.MiddleCenter, useSecondaryTextColor: true);
            var bodyLe = _body.GetComponent<LayoutElement>() ?? _body.gameObject.AddComponent<LayoutElement>();
            bodyLe.minHeight = 18f;
            bodyLe.preferredHeight = 22f;

            var share = FrUiFactory.AddButton(bottom.transform, "Share with friends", t, ShareLook,
                FrButtonEmphasis.Primary);
            ShrinkAction(share, 48f);

            var real = FrUiFactory.AddButton(bottom.transform, "Create Real Design", t, OpenTechPack,
                FrButtonEmphasis.AiAction);
            ShrinkAction(real, 52f);

            var row = new GameObject("Actions", typeof(RectTransform), typeof(HorizontalLayoutGroup),
                typeof(LayoutElement));
            row.transform.SetParent(bottom.transform, false);
            var rowLe = row.GetComponent<LayoutElement>();
            rowLe.minHeight = 44f;
            rowLe.preferredHeight = 44f;
            rowLe.flexibleWidth = 1f;
            var rowH = row.GetComponent<HorizontalLayoutGroup>();
            rowH.spacing = 8f;
            rowH.childAlignment = TextAnchor.MiddleCenter;
            rowH.childControlWidth = true;
            rowH.childForceExpandWidth = true;
            rowH.childControlHeight = true;
            rowH.childForceExpandHeight = true;

            var magicAgain = FrUiFactory.AddButton(row.transform, "Magic again", t, MagicAgain);
            ShrinkAction(magicAgain, 44f);
            var edit = FrUiFactory.AddButton(row.transform, "Edit sketch", t, EditSketch);
            ShrinkAction(edit, 44f);
            var home = FrUiFactory.AddButton(row.transform, "Home", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.NavigateToAsync(ScreenId.HomeDashboard);
            }, FrButtonEmphasis.Ghost);
            ShrinkAction(home, 44f);

            var stage = new GameObject("LookStage", typeof(RectTransform), typeof(Image));
            stage.transform.SetParent(root, false);
            _previewHost = stage.GetComponent<RectTransform>();
            _previewHost.anchorMin = new Vector2(0f, 0f);
            _previewHost.anchorMax = new Vector2(1f, 1f);
            _previewHost.offsetMin = new Vector2(20f, bottomH + 6f);
            _previewHost.offsetMax = new Vector2(-20f, -78f);
            var stageImg = stage.GetComponent<Image>();
            stageImg.sprite = FrUiSprites.RoundSoft;
            stageImg.type = Image.Type.Sliced;
            stageImg.color = new Color(1f, 1f, 1f, 0.55f);
            var stageShadow = stage.AddComponent<Shadow>();
            stageShadow.effectColor = new Color(0.08f, 0.07f, 0.06f, 0.14f);
            stageShadow.effectDistance = new Vector2(0f, -8f);

            var previewGo = new GameObject("LookPreview", typeof(RectTransform), typeof(RawImage),
                typeof(AspectRatioFitter));
            previewGo.transform.SetParent(stage.transform, false);
            var previewRt = previewGo.GetComponent<RectTransform>();
            previewRt.anchorMin = new Vector2(0.5f, 0f);
            previewRt.anchorMax = new Vector2(0.5f, 1f);
            previewRt.pivot = new Vector2(0.5f, 0.5f);
            previewRt.offsetMin = new Vector2(0f, 10f);
            previewRt.offsetMax = new Vector2(0f, -10f);
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

        void MagicAgain()
        {
            App.CreateDesign.ClearLastLook();
            App.CreateDesign.ClearTechPack();
            if (App.Navigation != null)
                _ = App.Navigation.NavigateToAsync(ScreenId.SketchEnhancement,
                    new SketchNavContext { AutoMagic = true, RestoreSketch = true });
        }

        void OpenTechPack()
        {
            if (App.Navigation == null)
                return;
            FrDiag.Step("create real design pressed");
            FrDiag.Fire(App.Navigation.NavigateToAsync(ScreenId.TechPack), "navigate TechPack");
        }

        public override async Task ShowAsync(object? payload = null, CancellationToken cancellationToken = default)
        {
            gameObject.SetActive(true);
            ClearPreviewTexture();
            SetPreviewVisible(false);

            var sb = new StringBuilder();
            sb.Append("Share it · refine with Magic · or build a real tech pack.");
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
                    sb.Insert(0, firstLine + "  ");
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
                return req.error ?? "download failed";

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
