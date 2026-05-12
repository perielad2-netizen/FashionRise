using System;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Content;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.Infrastructure.Platform;
using FashionRise.UI;
using Newtonsoft.Json.Linq;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class DesignDetailScreen : ScreenBase
    {
        Text _body = null!;
        RawImage _preview = null!;
        InputField _commentInput = null!;
        string _lastSpecSheetPdfUrl = "";

        public override ScreenId Id => ScreenId.DesignDetail;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Design detail", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            _body = FrUiFactory.AddLabel(col, "B", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperLeft);

            var previewGo = new GameObject("Preview", typeof(RectTransform), typeof(RawImage));
            previewGo.transform.SetParent(col, false);
            _preview = previewGo.GetComponent<RawImage>();
            _preview.raycastTarget = false;
            _preview.color = Color.white;
            var previewLe = previewGo.AddComponent<LayoutElement>();
            previewLe.preferredHeight = 220f;
            previewLe.minHeight = 0f;
            previewLe.flexibleWidth = 1f;
            previewGo.SetActive(false);

            FrUiFactory.AddLabel(col, "RateHint", "Your rating (1–10, signed in):", t,
                Mathf.RoundToInt(t.BodySize * 0.9f), FontStyle.Italic, TextAnchor.UpperCenter,
                useSecondaryTextColor: true);
            AddRatingRow(col, t, 1, 5);
            AddRatingRow(col, t, 6, 10);

            FrUiFactory.AddButton(col, "Toggle like", t, async () =>
            {
                var ctx = _ctx;
                if (ctx == null || string.IsNullOrEmpty(App.Auth.CurrentSessionUserId))
                {
                    _body.text = "Sign in to like.";
                    return;
                }

                try
                {
                    var item = await App.Gallery.GetByIdAsync(ctx.GalleryItemId).ConfigureAwait(true);
                    if (item == null)
                        return;
                    if (item.LikedByMe)
                        await App.Gallery.UnlikeAsync(ctx.GalleryItemId).ConfigureAwait(true);
                    else
                        await App.Gallery.LikeAsync(ctx.GalleryItemId).ConfigureAwait(true);
                }
                catch (System.Exception ex)
                {
                    _body.text = $"Like failed: {ex.Message}";
                    return;
                }

                await ReloadAsync().ConfigureAwait(true);
            });

            FrUiFactory.AddButton(col, "Follow creator", t, async () =>
            {
                if (_loadedItem == null || string.IsNullOrEmpty(App.Auth.CurrentSessionUserId))
                {
                    _body.text = "Sign in to follow.";
                    return;
                }

                if (string.Equals(App.Auth.CurrentSessionUserId, _loadedItem.OwnerUserId,
                        System.StringComparison.OrdinalIgnoreCase))
                {
                    _body.text = "You cannot follow yourself.";
                    return;
                }

                try
                {
                    await App.Follow.FollowAsync(_loadedItem.OwnerUserId).ConfigureAwait(true);
                }
                catch (System.Exception ex)
                {
                    _body.text = $"Follow failed: {ex.Message}";
                    return;
                }

                await ReloadAsync().ConfigureAwait(true);
            });

            FrUiFactory.AddButton(col, "Unfollow creator", t, async () =>
            {
                if (_loadedItem == null || string.IsNullOrEmpty(App.Auth.CurrentSessionUserId))
                {
                    _body.text = "Sign in to unfollow.";
                    return;
                }

                try
                {
                    await App.Follow.UnfollowAsync(_loadedItem.OwnerUserId).ConfigureAwait(true);
                }
                catch (System.Exception ex)
                {
                    _body.text = $"Unfollow failed: {ex.Message}";
                    return;
                }

                await ReloadAsync().ConfigureAwait(true);
            });

            FrUiFactory.AddButton(col, "Open creator's public gallery", t, () =>
            {
                if (_loadedItem == null || App.Navigation == null)
                    return;
                _ = App.Navigation.NavigateToAsync(ScreenId.Gallery,
                    new GalleryNavContext { OwnerUserId = _loadedItem.OwnerUserId });
            });

            FrUiFactory.AddLabel(col, "CommentHint", "Comment (signed in):", t,
                Mathf.RoundToInt(t.BodySize * 0.9f), FontStyle.Italic, TextAnchor.UpperLeft,
                useSecondaryTextColor: true);
            _commentInput = FrUiFactory.AddInputField(col, "CommentBody", "Write a comment…", t,
                Mathf.RoundToInt(t.BodySize));
            _commentInput.lineType = InputField.LineType.MultiLineNewline;
            _commentInput.characterLimit = 4000;
            var commentLe = _commentInput.gameObject.GetComponent<LayoutElement>();
            if (commentLe != null)
            {
                commentLe.minHeight = 100f;
                commentLe.preferredHeight = 100f;
            }

            FrUiFactory.AddButton(col, "Post comment", t, async () => { await PostCommentAsync(); });

            FrUiFactory.AddButton(col, "Copy share link", t, CopyShareLink);
            FrUiFactory.AddButton(col, "Share link...", t, ShareLinkNative);
            FrUiFactory.AddButton(col, "Copy share card (text + optional image URL)", t, CopyShareCard);
            FrUiFactory.AddButton(col, "Share card...", t, ShareCardNative);
            FrUiFactory.AddButton(col, "Copy maker handoff (JSON)", t, async () => { await CopyMakerHandoffAsync(); });
            FrUiFactory.AddButton(col, "Copy spec sheet (JSON)", t, async () => { await CopySpecSheetHandoffAsync(); });
            FrUiFactory.AddButton(col, "Generate spec sheet PDF (placeholder)", t,
                async () => { await GenerateSpecSheetPdfPlaceholderAsync(); });
            FrUiFactory.AddButton(col, "Open last spec sheet PDF URL", t, OpenLastSpecSheetPdfUrl);
            FrUiFactory.AddButton(col, "Share last spec sheet PDF URL", t, ShareLastSpecSheetPdfUrl);
            FrUiFactory.AddButton(col, "Download last spec sheet PDF", t, async () => { await DownloadLastSpecSheetPdfAsync(); });
            if (PcHandoffsFolderOpener.IsSupported)
                FrUiFactory.AddButton(col, "Open Handoffs folder (PC)", t, PcHandoffsFolderOpener.TryOpenHandoffsFolder);
            FrUiFactory.AddButton(col, "Save maker handoff to file", t, async () => { await SaveMakerHandoffToFileAsync(); });

            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        DesignDetailNavContext? _ctx;
        GalleryItem? _loadedItem;

        void OnDestroy() => ClearPreviewTexture();

        void ClearPreviewTexture()
        {
            if (_preview == null)
                return;
            if (_preview.texture != null)
            {
                Destroy(_preview.texture);
                _preview.texture = null!;
            }

            _preview.gameObject.SetActive(false);
        }

        async Task TryLoadPreviewAsync(GalleryItem item, CancellationToken cancellationToken)
        {
            ClearPreviewTexture();
            var url = item.ThumbnailPlaceholderKey?.Trim() ?? "";
            if (string.IsNullOrEmpty(url) ||
                !(url.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
                  url.StartsWith("https://", StringComparison.OrdinalIgnoreCase)))
                return;

            using var req = UnityWebRequestTexture.GetTexture(url);
            var op = req.SendWebRequest();
            while (!op.isDone)
                await Task.Delay(32, cancellationToken).ConfigureAwait(true);

            cancellationToken.ThrowIfCancellationRequested();
            if (req.result != UnityWebRequest.Result.Success)
                return;

            var tex = DownloadHandlerTexture.GetContent(req);
            if (tex == null)
                return;

            _preview.texture = tex;
            _preview.gameObject.SetActive(true);
        }

        async Task PostCommentAsync()
        {
            var ctx = _ctx;
            if (ctx == null || string.IsNullOrEmpty(App.Auth.CurrentSessionUserId))
            {
                _body.text = "Sign in to comment.";
                return;
            }

            var raw = _commentInput != null ? _commentInput.text : "";
            var body = (raw ?? "").Trim();
            if (body.Length == 0)
            {
                await ReloadAsync().ConfigureAwait(true);
                _body.text += "\n\nEnter comment text above, then tap Post comment.";
                return;
            }

            if (body.Length > 4000)
                body = body.Substring(0, 4000);

            try
            {
                await App.Gallery.PostCommentAsync(ctx.GalleryItemId, body).ConfigureAwait(true);
            }
            catch (Exception ex)
            {
                _body.text = $"Comment failed: {ex.Message}";
                return;
            }

            if (_commentInput != null)
                _commentInput.text = "";
            await ReloadAsync().ConfigureAwait(true);
        }

        void CopyShareLink()
        {
            if (_loadedItem == null)
                return;
            ShareClipboard.Copy(App.ShareLinks.BuildGalleryItemUrl(_loadedItem.Id));
            _body.text += "\n\n(Share link copied to clipboard.)";
        }

        void CopyShareCard()
        {
            if (_loadedItem == null)
                return;
            var img = string.IsNullOrEmpty(_loadedItem.ThumbnailPlaceholderKey)
                ? null
                : _loadedItem.ThumbnailPlaceholderKey;
            ShareClipboard.Copy(App.ShareLinks.BuildShareCardText(_loadedItem.Title, _loadedItem.Id, img));
            _body.text += "\n\n(Share card copied to clipboard.)";
        }

        void ShareLinkNative()
        {
            if (_loadedItem == null)
                return;
            var url = App.ShareLinks.BuildGalleryItemUrl(_loadedItem.Id);
            if (NativeShareSheet.TryShareText(url, "FashionRise design link"))
                _body.text += "\n\n(Opened native share options for link.)";
            else
            {
                ShareClipboard.Copy(url);
                _body.text += "\n\n(Native share unavailable; link copied to clipboard.)";
            }
        }

        void ShareCardNative()
        {
            if (_loadedItem == null)
                return;
            var img = string.IsNullOrEmpty(_loadedItem.ThumbnailPlaceholderKey)
                ? null
                : _loadedItem.ThumbnailPlaceholderKey;
            var card = App.ShareLinks.BuildShareCardText(_loadedItem.Title, _loadedItem.Id, img);
            if (NativeShareSheet.TryShareText(card, "FashionRise share card"))
                _body.text += "\n\n(Opened native share options for card.)";
            else
            {
                ShareClipboard.Copy(card);
                _body.text += "\n\n(Native share unavailable; card copied to clipboard.)";
            }
        }

        async Task<(bool ok, string? json, string error)> TryGetOwnerHandoffJsonAsync(string exportKind = "manifest_v1")
        {
            if (_loadedItem == null)
                return (false, null, "Nothing loaded yet.");

            if (string.IsNullOrEmpty(App.Auth.CurrentSessionUserId))
                return (false, null, "Sign in to export handoff.");

            if (!string.Equals(App.Auth.CurrentSessionUserId, _loadedItem.OwnerUserId,
                    StringComparison.OrdinalIgnoreCase))
                return (false, null, "Maker handoff is only available for your own published designs.");

            if (App.IsApiBackend && !App.Auth.HasBackendSession)
                return (false, null, "Use API sign-in to fetch handoff from the server.");

            try
            {
                var json = await App.Handoff.GetHandoffManifestJsonAsync(_loadedItem.DesignId, exportKind)
                    .ConfigureAwait(true);
                if (string.IsNullOrEmpty(json))
                    return (false, null, "Handoff not available (design not found).");

                return (true, json, "");
            }
            catch (Exception ex)
            {
                return (false, null, $"Handoff failed: {ex.Message}");
            }
        }

        static string SanitizeHandoffFileSegment(string designId)
        {
            if (string.IsNullOrEmpty(designId))
                return "design";
            var sb = new StringBuilder(designId.Length);
            foreach (var ch in designId)
            {
                if (char.IsLetterOrDigit(ch) || ch is '_' or '-')
                    sb.Append(ch);
                else
                    sb.Append('_');
            }

            return sb.Length > 0 ? sb.ToString() : "design";
        }

        void AddRatingRow(Transform parent, FashionRiseTheme t, int fromInclusive, int toInclusive)
        {
            var rowGo = new GameObject($"RateRow_{fromInclusive}_{toInclusive}", typeof(RectTransform),
                typeof(HorizontalLayoutGroup));
            rowGo.transform.SetParent(parent, false);
            var hl = rowGo.GetComponent<HorizontalLayoutGroup>();
            hl.spacing = Mathf.Max(6f, t.ControlGap * 0.45f);
            hl.childAlignment = TextAnchor.MiddleCenter;
            hl.childControlWidth = true;
            hl.childForceExpandWidth = true;
            hl.childControlHeight = true;
            hl.childForceExpandHeight = false;
            var rowRt = rowGo.GetComponent<RectTransform>();
            rowRt.sizeDelta = new Vector2(0f, 48f);

            for (var s = fromInclusive; s <= toInclusive; s++)
            {
                var score = s;
                FrUiFactory.AddButton(rowGo.transform, score.ToString(), t, async () =>
                {
                    var ctx = _ctx;
                    if (ctx == null)
                        return;

                    if (string.IsNullOrEmpty(App.Auth.CurrentSessionUserId))
                    {
                        _body.text = "Sign in to rate.";
                        return;
                    }

                    try
                    {
                        await App.Ratings.SubmitRatingAsync(ctx.GalleryItemId, score).ConfigureAwait(true);
                    }
                    catch (Exception ex)
                    {
                        _body.text = $"Rating failed: {ex.Message}";
                        return;
                    }

                    await ReloadAsync().ConfigureAwait(true);
                });
            }
        }

        async Task CopyMakerHandoffAsync()
        {
            var (ok, json, error) = await TryGetOwnerHandoffJsonAsync().ConfigureAwait(true);
            if (!ok || json == null)
            {
                _body.text = error;
                return;
            }

            ShareClipboard.Copy(json);
            _body.text += "\n\nMaker handoff JSON copied to clipboard.";
        }

        async Task CopySpecSheetHandoffAsync()
        {
            var (ok, json, error) = await TryGetOwnerHandoffJsonAsync("spec_sheet_v1").ConfigureAwait(true);
            if (!ok || json == null)
            {
                _body.text = error;
                return;
            }

            ShareClipboard.Copy(json);
            _body.text += "\n\nSpec sheet JSON copied to clipboard.";
        }

        async Task GenerateSpecSheetPdfPlaceholderAsync()
        {
            var (ok, json, error) = await TryGetOwnerHandoffJsonAsync("spec_sheet_pdf").ConfigureAwait(true);
            if (!ok || json == null)
            {
                _body.text = error;
                return;
            }

            ShareClipboard.Copy(json);
            _body.text += "\n\nSpec sheet PDF placeholder payload copied to clipboard.";
            var fileUrl = TryExtractExportFileUrl(json);
            if (!string.IsNullOrEmpty(fileUrl))
            {
                _lastSpecSheetPdfUrl = fileUrl;
                _body.text += $"\nPDF file URL:\n{fileUrl}";
            }
        }

        void OpenLastSpecSheetPdfUrl()
        {
            if (string.IsNullOrEmpty(_lastSpecSheetPdfUrl))
            {
                _body.text += "\n\nGenerate spec sheet PDF first to get a URL.";
                return;
            }

            UnityEngine.Application.OpenURL(_lastSpecSheetPdfUrl);
            _body.text += $"\n\nOpened PDF URL:\n{_lastSpecSheetPdfUrl}";
        }

        void ShareLastSpecSheetPdfUrl()
        {
            if (string.IsNullOrEmpty(_lastSpecSheetPdfUrl))
            {
                _body.text += "\n\nGenerate spec sheet PDF first to get a URL.";
                return;
            }

            if (NativeShareSheet.TryShareText(_lastSpecSheetPdfUrl, "FashionRise spec sheet PDF"))
                _body.text += "\n\nOpened native share options for PDF URL.";
            else
            {
                ShareClipboard.Copy(_lastSpecSheetPdfUrl);
                _body.text += $"\n\nNative share unavailable here; copied PDF URL:\n{_lastSpecSheetPdfUrl}";
            }
        }

        async Task DownloadLastSpecSheetPdfAsync()
        {
            var url = _lastSpecSheetPdfUrl?.Trim() ?? "";
            if (string.IsNullOrEmpty(url))
            {
                _body.text += "\n\nGenerate spec sheet PDF first to get a URL.";
                return;
            }

            if (!(url.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
                  url.StartsWith("https://", StringComparison.OrdinalIgnoreCase)))
            {
                _body.text += "\n\nSpec sheet PDF URL is not a web URL.";
                return;
            }

            try
            {
                using var req = UnityWebRequest.Get(url);
                req.timeout = 30;
                var op = req.SendWebRequest();
                while (!op.isDone)
                    await Task.Delay(32).ConfigureAwait(true);

                if (req.result != UnityWebRequest.Result.Success)
                {
                    _body.text += $"\n\nPDF download failed: {req.error}";
                    return;
                }

                var bytes = req.downloadHandler.data;
                if (bytes == null || bytes.Length == 0)
                {
                    _body.text += "\n\nPDF download failed: empty file.";
                    return;
                }

                var designPart = _loadedItem != null ? SanitizeHandoffFileSegment(_loadedItem.DesignId) : "design";
                var dir = Path.Combine(UnityEngine.Application.persistentDataPath, "Handoffs");
                Directory.CreateDirectory(dir);
                var path = Path.Combine(dir, $"spec_sheet_{designPart}_{DateTime.UtcNow:yyyyMMdd_HHmmss}.pdf");
                File.WriteAllBytes(path, bytes);
                _body.text += $"\n\nSpec sheet PDF downloaded to:\n{path}";
            }
            catch (Exception ex)
            {
                _body.text += $"\n\nPDF download failed: {ex.Message}";
            }
        }

        static string? TryExtractExportFileUrl(string json)
        {
            try
            {
                var obj = JObject.Parse(json);
                return obj["export"]?["file_url"]?.Value<string>();
            }
            catch
            {
                return null;
            }
        }

        async Task SaveMakerHandoffToFileAsync()
        {
            var (ok, json, error) = await TryGetOwnerHandoffJsonAsync().ConfigureAwait(true);
            if (!ok || json == null)
            {
                _body.text = error;
                return;
            }

            try
            {
                var dir = Path.Combine(UnityEngine.Application.persistentDataPath, "Handoffs");
                Directory.CreateDirectory(dir);
                var fileName = $"handoff_{SanitizeHandoffFileSegment(_loadedItem!.DesignId)}.json";
                var path = Path.Combine(dir, fileName);
                File.WriteAllText(path, json, new UTF8Encoding(encoderShouldEmitUTF8Identifier: false));
                _body.text += $"\n\nMaker handoff saved to file:\n{path}";
            }
            catch (Exception ex)
            {
                _body.text += $"\n\nCould not save handoff file: {ex.Message}";
            }
        }

        protected override void OnShown(object? payload)
        {
            _ctx = payload as DesignDetailNavContext;
            _ = ReloadAsync();
        }

        async Task ReloadAsync(CancellationToken cancellationToken = default)
        {
            _loadedItem = null;
            ClearPreviewTexture();
            if (_ctx == null)
            {
                _body.text = "No gallery context.";
                return;
            }

            _body.text = "Loading…";
            try
            {
                var item = await App.Gallery.GetByIdAsync(_ctx.GalleryItemId, cancellationToken)
                    .ConfigureAwait(true);
                if (item == null)
                {
                    _body.text = "Item not found.";
                    return;
                }

                _loadedItem = item;

                var summary = await App.Ratings.GetSummaryAsync(item.Id, cancellationToken).ConfigureAwait(true);
                var design = await App.DesignSave.GetDesignByIdAsync(item.DesignId, cancellationToken)
                    .ConfigureAwait(true);
                var designLine = design != null
                    ? $"Design: {design.Metadata.Title}\nCategory: {design.Category}\n"
                    : $"Design id: {item.DesignId}\n";

                var comments = await App.Gallery.GetCommentsAsync(item.Id, cancellationToken).ConfigureAwait(true);
                var sb = new StringBuilder();
                sb.AppendLine($"{item.Title}");
                sb.AppendLine($"Owner: {item.OwnerUserId}");
                sb.AppendLine($"Likes: {item.LikesCount}  You liked: {item.LikedByMe}");
                sb.AppendLine(designLine);
                sb.AppendLine($"Rating: {summary.Average:0.00} / 10 ({summary.Count})");
                var self = App.Auth.CurrentSessionUserId;
                if (!string.IsNullOrEmpty(self) &&
                    string.Equals(self, item.OwnerUserId, System.StringComparison.OrdinalIgnoreCase))
                    sb.AppendLine("This is your published design.");
                else if (!string.IsNullOrEmpty(self))
                {
                    var following = await App.Follow.IsFollowingAsync(item.OwnerUserId, cancellationToken)
                        .ConfigureAwait(true);
                    sb.AppendLine(following ? "You follow this creator." : "You do not follow this creator yet.");
                }

                sb.AppendLine("Comments:");
                if (comments.Count == 0)
                    sb.AppendLine("— none —");
                else
                    foreach (var c in comments)
                    {
                        var who = c.AuthorUserId.Length <= 8
                            ? c.AuthorUserId
                            : c.AuthorUserId[..8] + "…";
                        sb.AppendLine($"• {who}  {c.Body}");
                    }

                _body.text = sb.ToString();
                await TryLoadPreviewAsync(item, cancellationToken).ConfigureAwait(true);
            }
            catch (System.Exception ex)
            {
                _loadedItem = null;
                ClearPreviewTexture();
                _body.text = $"Could not load detail.\n{ex.Message}";
            }
        }
    }
}
