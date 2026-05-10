using System.Text;
using FashionRise.Core.Navigation;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class DesignDetailScreen : ScreenBase
    {
        Text _body = null!;

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

            FrUiFactory.AddButton(col, "Rate 8 / 10", t, async () =>
            {
                var ctx = _ctx;
                if (ctx == null)
                    return;
                try
                {
                    await App.Ratings.SubmitRatingAsync(ctx.GalleryItemId, 8).ConfigureAwait(true);
                }
                catch (System.Exception ex)
                {
                    _body.text = $"Rating failed: {ex.Message}";
                    return;
                }

                await ReloadAsync().ConfigureAwait(true);
            });

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

            FrUiFactory.AddButton(col, "Add comment (signed in)", t, async () =>
            {
                var ctx = _ctx;
                if (ctx == null || string.IsNullOrEmpty(App.Auth.CurrentSessionUserId))
                {
                    _body.text = "Sign in to comment.";
                    return;
                }

                try
                {
                    await App.Gallery.PostCommentAsync(ctx.GalleryItemId, "Lovely drape — mock comment.")
                        .ConfigureAwait(true);
                }
                catch (System.Exception ex)
                {
                    _body.text = $"Comment failed: {ex.Message}";
                    return;
                }

                await ReloadAsync().ConfigureAwait(true);
            });

            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        DesignDetailNavContext? _ctx;

        protected override void OnShown(object? payload)
        {
            _ctx = payload as DesignDetailNavContext;
            _ = ReloadAsync();
        }

        async System.Threading.Tasks.Task ReloadAsync()
        {
            if (_ctx == null)
            {
                _body.text = "No gallery context.";
                return;
            }

            _body.text = "Loading…";
            try
            {
                var item = await App.Gallery.GetByIdAsync(_ctx.GalleryItemId).ConfigureAwait(true);
                if (item == null)
                {
                    _body.text = "Item not found.";
                    return;
                }

                var summary = await App.Ratings.GetSummaryAsync(item.Id).ConfigureAwait(true);
                var design = await App.DesignSave.GetDesignByIdAsync(item.DesignId).ConfigureAwait(true);
                var designLine = design != null
                    ? $"Design: {design.Metadata.Title}\nCategory: {design.Category}\n"
                    : $"Design id: {item.DesignId}\n";

                var comments = await App.Gallery.GetCommentsAsync(item.Id).ConfigureAwait(true);
                var sb = new StringBuilder();
                sb.AppendLine($"{item.Title}");
                sb.AppendLine($"Owner: {item.OwnerUserId}");
                sb.AppendLine($"Likes: {item.LikesCount}  You liked: {item.LikedByMe}");
                sb.AppendLine(designLine);
                sb.AppendLine($"Rating: {summary.Average:0.00} / 10 ({summary.Count})");
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
            }
            catch (System.Exception ex)
            {
                _body.text = $"Could not load detail.\n{ex.Message}";
            }
        }
    }
}
