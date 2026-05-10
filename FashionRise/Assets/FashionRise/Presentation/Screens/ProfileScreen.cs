using System.Text;
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

            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        protected override async void OnShown(object? payload)
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
                sb.AppendLine($"Designs: {s.DesignCount}  Published: {s.PublishedCount}");
                sb.AppendLine($"Avg rating: {s.AverageRating:0.0} ({s.RatingCount} ratings)");
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
