using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class GalleryScreen : ScreenBase
    {
        RectTransform _list = null!;
        Text _sortLabel = null!;
        GallerySort _sort = GallerySort.Newest;

        public override ScreenId Id => ScreenId.Gallery;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Gallery", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            _sortLabel = FrUiFactory.AddLabel(col, "Sort", "Sort: Newest", t, Mathf.RoundToInt(t.BodySize),
                FontStyle.Italic, TextAnchor.UpperCenter);
            FrUiFactory.AddButton(col, "Cycle sort (newest / top / trending)", t, () =>
            {
                _sort = _sort switch
                {
                    GallerySort.Newest => GallerySort.TopRated,
                    GallerySort.TopRated => GallerySort.Trending,
                    _ => GallerySort.Newest
                };
                _sortLabel.text = _sort switch
                {
                    GallerySort.TopRated => "Sort: Top rated",
                    GallerySort.Trending => "Sort: Trending (likes-heavy)",
                    _ => "Sort: Newest"
                };
                Reload();
            });

            var listGo = new GameObject("List", typeof(RectTransform), typeof(VerticalLayoutGroup));
            _list = listGo.GetComponent<RectTransform>();
            _list.SetParent(col, false);
            var v = listGo.GetComponent<VerticalLayoutGroup>();
            v.spacing = t.ControlGap;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;

            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        protected override void OnShown(object? payload) => Reload();

        async void Reload()
        {
            foreach (Transform c in _list)
                Destroy(c.gameObject);

            var t = ThemeOrDefault;
            try
            {
                var feed = await App.Gallery.GetFeedAsync(_sort).ConfigureAwait(true);
                if (feed.Count == 0)
                    FrUiFactory.AddLabel(_list, "Empty", "No public gallery items yet.", t,
                        Mathf.RoundToInt(t.BodySize), FontStyle.Italic, TextAnchor.UpperCenter);
                foreach (var item in feed)
                {
                    var id = item.Id;
                    var label = $"{item.Title} — ★ {item.Rating.Average:0.0}  ♥ {item.LikesCount}";
                    FrUiFactory.AddButton(_list, label, t, () =>
                    {
                        if (App.Navigation != null)
                            _ = App.Navigation.NavigateToAsync(ScreenId.DesignDetail,
                                new DesignDetailNavContext { GalleryItemId = id });
                    });
                }
            }
            catch (System.Exception ex)
            {
                FrUiFactory.AddLabel(_list, "Err", $"Gallery unavailable.\n{ex.Message}", t,
                    Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter);
            }
        }
    }
}
