using System.Text;
using System.Threading.Tasks;
using FashionRise.Core.Navigation;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class ProfileScreen : ScreenBase
    {
        Text _body = null!;

        public override ScreenId Id => ScreenId.Profile;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Profile", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            _body = FrUiFactory.AddLabel(col, "B", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperLeft);

            FrUiFactory.AddButton(col, "Refresh", t, () => { _ = ReloadAsync(); });
            FrUiFactory.AddButton(col, "My public gallery", t, () => { _ = OpenMyPublicGalleryAsync(); });
            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        protected override void OnShown(object? payload) => _ = ReloadAsync();

        async Task OpenMyPublicGalleryAsync()
        {
            var uid = App.Auth.CurrentSessionUserId;
            if (string.IsNullOrEmpty(uid))
            {
                await ReloadAsync().ConfigureAwait(true);
                _body.text += "\n\nSign in to open your public gallery.";
                return;
            }

            if (App.Navigation != null)
                await App.Navigation
                    .NavigateToAsync(ScreenId.Gallery, new GalleryNavContext { OwnerUserId = uid })
                    .ConfigureAwait(true);
        }

        async Task ReloadAsync()
        {
            _body.text = "Loading…";
            try
            {
                var p = await App.UserProfile.GetMyProfileAsync().ConfigureAwait(true);
                var s = await App.UserProfile.GetMyStatsAsync().ConfigureAwait(true);
                var sb = new StringBuilder();
                sb.AppendLine($"{p.DisplayName}");
                sb.AppendLine($"{p.Bio}");
                sb.AppendLine();
                sb.AppendLine($"Reputation: {p.ReputationScore:0.0} ({p.ReputationTier})");
                sb.AppendLine($"Followers: {p.FollowersCount}");
                sb.AppendLine($"Designs: {s.DesignCount}  Published: {s.PublishedCount}");
                sb.AppendLine($"Avg rating: {s.AverageRating:0.0} ({s.RatingCount} ratings)");

                var followingCount = 0;
                if (!string.IsNullOrEmpty(App.Auth.CurrentSessionUserId))
                {
                    try
                    {
                        var ids = await App.Follow.GetFollowedUserIdsAsync().ConfigureAwait(true);
                        followingCount = ids.Count;
                    }
                    catch
                    {
                        /* offline / transient */
                    }
                }

                sb.AppendLine(
                    string.IsNullOrEmpty(App.Auth.CurrentSessionUserId)
                        ? "Following: — (sign in)"
                        : $"Following: {followingCount} creator(s)");
                sb.AppendLine();
                sb.AppendLine("My designs (API mode when signed in):");

                if (App.IsApiBackend && !string.IsNullOrEmpty(App.Auth.CurrentSessionUserId))
                {
                    var mine = await App.DesignSave.ListMyDesignsAsync().ConfigureAwait(true);
                    if (mine.Count == 0)
                        sb.AppendLine("— none —");
                    else
                        foreach (var d in mine)
                            sb.AppendLine($"• {d.Metadata.Title}  [{d.Category}]  {d.Status}");
                }
                else
                {
                    sb.AppendLine("Use API backend + account to load cloud drafts here.");
                }

                _body.text = sb.ToString();
            }
            catch (System.Exception ex)
            {
                _body.text = $"Could not load profile.\n{ex.Message}";
            }
        }
    }
}
