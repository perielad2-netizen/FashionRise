using System;
using System.Collections.Generic;
using FashionRise.Core.Navigation;
using FashionRise.Domain;
using FashionRise.Infrastructure.Api;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    /// <summary>Pillar B — gallery feed: newest, top rated, trending, and signed-in following feed.</summary>
    public sealed class GalleryScreen : ScreenBase
    {
        RectTransform _list = null!;
        Text _title = null!;
        Text _sub = null!;
        Text _sortLabel = null!;
        GameObject _sortRowGo = null!;
        Button _communityFeedBtn = null!;
        GallerySort _sort = GallerySort.Newest;
        string? _filterOwnerUserId;

        public override ScreenId Id => ScreenId.Gallery;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            _title = FrUiFactory.AddLabel(col, "H", "Gallery", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            _sub = FrUiFactory.AddLabel(col, "Sub", "Public designs from the community — rate, like, and comment.", t,
                Mathf.RoundToInt(t.BodySize * 0.95f), FontStyle.Normal, TextAnchor.UpperCenter,
                useSecondaryTextColor: true);

            _sortLabel = FrUiFactory.AddLabel(col, "Sort", "", t, Mathf.RoundToInt(t.BodySize * 0.9f),
                FontStyle.Italic, TextAnchor.UpperCenter);

            _sortRowGo = new GameObject("SortRow", typeof(RectTransform), typeof(HorizontalLayoutGroup));
            _sortRowGo.transform.SetParent(col, false);
            var hl = _sortRowGo.GetComponent<HorizontalLayoutGroup>();
            hl.spacing = Mathf.Max(6f, t.ControlGap * 0.45f);
            hl.childAlignment = TextAnchor.MiddleCenter;
            hl.childControlWidth = true;
            hl.childForceExpandWidth = true;
            hl.childControlHeight = true;
            hl.childForceExpandHeight = false;
            var sortRowRt = _sortRowGo.GetComponent<RectTransform>();
            sortRowRt.sizeDelta = new Vector2(0f, 52f);

            void Pick(GallerySort s)
            {
                _sort = s;
                SyncSortLabel();
                Reload();
            }

            FrUiFactory.AddButton(_sortRowGo.transform, "Newest", t, () => Pick(GallerySort.Newest));
            FrUiFactory.AddButton(_sortRowGo.transform, "Top rated", t, () => Pick(GallerySort.TopRated));
            FrUiFactory.AddButton(_sortRowGo.transform, "Trending", t, () => Pick(GallerySort.Trending));
            FrUiFactory.AddButton(_sortRowGo.transform, "Following", t, () => Pick(GallerySort.Following));

            FrUiFactory.AddButton(col, "Refresh feed", t, () => Reload());
            _communityFeedBtn = FrUiFactory.AddButton(col, "Community feed (all creators)", t, () =>
            {
                if (string.IsNullOrEmpty(_filterOwnerUserId))
                    return;
                _filterOwnerUserId = null;
                ApplyModeChrome();
                Reload();
            });
            _communityFeedBtn.gameObject.SetActive(false);

            var listGo = new GameObject("List", typeof(RectTransform), typeof(VerticalLayoutGroup));
            _list = listGo.GetComponent<RectTransform>();
            _list.SetParent(col, false);
            var le = listGo.AddComponent<LayoutElement>();
            le.flexibleHeight = 1f;
            le.minHeight = 120f;
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

            SyncSortLabel();
        }

        protected override void OnShown(object? payload)
        {
            // Null payload (e.g. GoBack): keep _filterOwnerUserId and _sort so creator-filtered gallery survives return from detail.
            if (payload is GalleryNavContext ctx)
            {
                if (!string.IsNullOrWhiteSpace(ctx.OwnerUserId))
                    _filterOwnerUserId = ctx.OwnerUserId.Trim();
                else
                {
                    _filterOwnerUserId = null;
                    if (ctx.CommunitySort is GallerySort s)
                        _sort = s;
                }
            }

            ApplyModeChrome();
            Reload();
        }

        void ApplyModeChrome()
        {
            var filtered = !string.IsNullOrEmpty(_filterOwnerUserId);
            _sortLabel.gameObject.SetActive(!filtered);
            _sortRowGo.SetActive(!filtered);
            _communityFeedBtn.gameObject.SetActive(filtered);
            if (filtered)
            {
                _title.text = "Creator gallery";
                var hint = _filterOwnerUserId!.Length <= 13
                    ? _filterOwnerUserId
                    : _filterOwnerUserId[..8] + "…";
                _sub.text = $"Public posts from this creator ({hint}).";
            }
            else
            {
                _title.text = "Gallery";
                _sub.text = "Public designs from the community — rate, like, and comment.";
                SyncSortLabel();
            }
        }

        void SyncSortLabel()
        {
            _sortLabel.text = _sort switch
            {
                GallerySort.TopRated => "Showing: highest average rating first",
                GallerySort.Trending => "Showing: most likes, then rating, then newest",
                GallerySort.Following => App.Auth.HasBackendSession
                    ? "Showing: public posts from creators you follow (newest first)"
                    : "Following — sign in, then use Follow creator on a design to build this feed.",
                _ => "Showing: newest first"
            };
        }

        async void Reload()
        {
            foreach (Transform c in _list)
                Destroy(c.gameObject);

            var t = ThemeOrDefault;
            try
            {
                IReadOnlyList<GalleryItem> feed;
                if (!string.IsNullOrEmpty(_filterOwnerUserId))
                    feed = await App.Gallery.GetUserPublicGalleryAsync(_filterOwnerUserId).ConfigureAwait(true);
                else
                    feed = await App.Gallery.GetFeedAsync(_sort).ConfigureAwait(true);

                if (feed.Count == 0)
                {
                    string emptyMsg;
                    if (!string.IsNullOrEmpty(_filterOwnerUserId))
                        emptyMsg = "No public posts from this creator yet.";
                    else if (_sort == GallerySort.Following)
                        emptyMsg =
                            "No posts from people you follow yet. Open a public design and tap Follow creator.";
                    else
                        emptyMsg = "No public gallery items yet. Publish from Create design.";
                    FrUiFactory.AddLabel(_list, "Empty", emptyMsg, t, Mathf.RoundToInt(t.BodySize), FontStyle.Italic,
                        TextAnchor.UpperCenter);
                }

                foreach (var item in feed)
                {
                    var id = item.Id;
                    var u = item.ThumbnailPlaceholderKey?.Trim() ?? "";
                    var hasPreview = u.StartsWith("http://", StringComparison.OrdinalIgnoreCase) ||
                                     u.StartsWith("https://", StringComparison.OrdinalIgnoreCase);
                    var label = $"{item.Title}{(hasPreview ? " [preview]" : "")} — ★ {item.Rating.Average:0.0}  ♥ {item.LikesCount}";
                    FrUiFactory.AddButton(_list, label, t, () =>
                    {
                        if (App.Navigation != null)
                            _ = App.Navigation.NavigateToAsync(ScreenId.DesignDetail,
                                new DesignDetailNavContext { GalleryItemId = id });
                    });
                }
            }
            catch (ApiException ex) when (ex.StatusCode == 401 && string.IsNullOrEmpty(_filterOwnerUserId))
            {
                FrUiFactory.AddLabel(_list, "Err",
                    "Sign in to load your following feed. Use Profile → login, then try again.",
                    t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter);
            }
            catch (System.Exception ex)
            {
                FrUiFactory.AddLabel(_list, "Err", $"Gallery unavailable.\n{ex.Message}", t,
                    Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter);
            }
        }
    }
}
