using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Domain;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockGalleryService : IGalleryService
    {
        readonly IAuthService _auth;
        readonly IFollowService _follow;
        readonly List<GalleryItem> _feed;
        readonly Dictionary<string, HashSet<string>> _likedByUser = new(StringComparer.Ordinal);
        readonly Dictionary<string, List<GalleryComment>> _comments = new(StringComparer.Ordinal);

        public MockGalleryService(IAuthService auth, IFollowService follow)
        {
            _auth = auth;
            _follow = follow;
            _feed = new List<GalleryItem>
            {
                new()
                {
                    Id = "gal_01",
                    OwnerUserId = "creator_a",
                    DesignId = "des_01",
                    Title = "Midnight satin column",
                    ThumbnailPlaceholderKey = "thumb/gal_01",
                    Rating = new RatingSummary { Average = 8.7, Count = 42, MyScore = null },
                    LikesCount = 12
                },
                new()
                {
                    Id = "gal_02",
                    OwnerUserId = "creator_b",
                    DesignId = "des_02",
                    Title = "Sea mist wrap blouse",
                    ThumbnailPlaceholderKey = "thumb/gal_02",
                    Rating = new RatingSummary { Average = 9.1, Count = 18, MyScore = 9 },
                    LikesCount = 30
                },
                new()
                {
                    Id = "gal_03",
                    OwnerUserId = "creator_c",
                    DesignId = "des_03",
                    Title = "Tailored wool coord",
                    ThumbnailPlaceholderKey = "thumb/gal_03",
                    Rating = new RatingSummary { Average = 7.8, Count = 9, MyScore = null },
                    LikesCount = 5
                }
            };
            foreach (var g in _feed)
                _comments[g.Id] = new List<GalleryComment>();
        }

        public async Task<IReadOnlyList<GalleryItem>> GetFeedAsync(GallerySort sort = GallerySort.Newest,
            CancellationToken cancellationToken = default)
        {
            IEnumerable<GalleryItem> q = _feed;
            if (sort == GallerySort.Following)
            {
                var ids = await _follow.GetFollowedUserIdsAsync(cancellationToken).ConfigureAwait(true);
                if (ids.Count == 0)
                    q = Array.Empty<GalleryItem>();
                else
                {
                    var set = new HashSet<string>(ids, StringComparer.Ordinal);
                    q = _feed.Where(x => set.Contains(x.OwnerUserId)).OrderByDescending(x => x.LikesCount);
                }
            }
            else
            {
                q = sort switch
                {
                    GallerySort.TopRated => q.OrderByDescending(x => x.Rating.Average),
                    GallerySort.Trending => q.OrderByDescending(x => x.LikesCount)
                        .ThenByDescending(x => x.Rating.Average),
                    _ => q.AsEnumerable()
                };
            }
            var uid = _auth.CurrentSessionUserId;
            var list = q.Select(CloneWithLikeState).ToList();
            if (!string.IsNullOrEmpty(uid) && _likedByUser.TryGetValue(uid, out var liked))
            {
                foreach (var item in list)
                    item.LikedByMe = liked.Contains(item.Id);
            }

            return list;
        }

        public Task<IReadOnlyList<GalleryItem>> GetUserPublicGalleryAsync(string ownerUserId,
            CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(ownerUserId))
                return Task.FromResult((IReadOnlyList<GalleryItem>)Array.Empty<GalleryItem>());
            var key = ownerUserId.Trim();
            IEnumerable<GalleryItem> q = _feed.Where(x =>
                string.Equals(x.OwnerUserId, key, StringComparison.Ordinal));
            q = q.OrderByDescending(x => x.Id);
            var uid = _auth.CurrentSessionUserId;
            var list = q.Select(CloneWithLikeState).ToList();
            if (!string.IsNullOrEmpty(uid) && _likedByUser.TryGetValue(uid, out var liked))
            {
                foreach (var item in list)
                    item.LikedByMe = liked.Contains(item.Id);
            }

            return Task.FromResult((IReadOnlyList<GalleryItem>)list);
        }

        public Task<GalleryItem?> GetByIdAsync(string galleryItemId,
            CancellationToken cancellationToken = default)
        {
            var raw = _feed.FirstOrDefault(x => x.Id == galleryItemId);
            if (raw == null)
                return Task.FromResult<GalleryItem?>(null);
            var copy = CloneWithLikeState(raw);
            var uid = _auth.CurrentSessionUserId;
            if (!string.IsNullOrEmpty(uid) && _likedByUser.TryGetValue(uid, out var liked))
                copy.LikedByMe = liked.Contains(copy.Id);
            return Task.FromResult<GalleryItem?>(copy);
        }

        static GalleryItem CloneWithLikeState(GalleryItem g) =>
            new()
            {
                Id = g.Id,
                OwnerUserId = g.OwnerUserId,
                DesignId = g.DesignId,
                Title = g.Title,
                ThumbnailPlaceholderKey = g.ThumbnailPlaceholderKey,
                Rating = g.Rating,
                LikesCount = g.LikesCount,
                LikedByMe = g.LikedByMe
            };

        public Task LikeAsync(string galleryItemId, CancellationToken cancellationToken = default)
        {
            var uid = _auth.CurrentSessionUserId;
            if (string.IsNullOrEmpty(uid))
                return Task.CompletedTask;
            var item = _feed.FirstOrDefault(x => x.Id == galleryItemId);
            if (item == null)
                return Task.CompletedTask;
            if (!_likedByUser.TryGetValue(uid, out var set))
            {
                set = new HashSet<string>(StringComparer.Ordinal);
                _likedByUser[uid] = set;
            }

            if (set.Add(galleryItemId))
                item.LikesCount++;
            return Task.CompletedTask;
        }

        public Task UnlikeAsync(string galleryItemId, CancellationToken cancellationToken = default)
        {
            var uid = _auth.CurrentSessionUserId;
            if (string.IsNullOrEmpty(uid))
                return Task.CompletedTask;
            var item = _feed.FirstOrDefault(x => x.Id == galleryItemId);
            if (item == null)
                return Task.CompletedTask;
            if (_likedByUser.TryGetValue(uid, out var set) && set.Remove(galleryItemId))
                item.LikesCount = Math.Max(0, item.LikesCount - 1);
            return Task.CompletedTask;
        }

        public Task<IReadOnlyList<GalleryComment>> GetCommentsAsync(string galleryItemId,
            CancellationToken cancellationToken = default)
        {
            if (!_comments.TryGetValue(galleryItemId, out var list))
                list = new List<GalleryComment>();
            return Task.FromResult((IReadOnlyList<GalleryComment>)list.ToList());
        }

        public Task<GalleryItem> PublishDesignAsync(string designId, string title, string? imageUrl,
            CancellationToken cancellationToken = default)
        {
            var uid = _auth.CurrentSessionUserId ?? "mock-user";
            var id = "gal_" + Guid.NewGuid().ToString("N")[..10];
            var item = new GalleryItem
            {
                Id = id,
                OwnerUserId = uid,
                DesignId = designId,
                Title = string.IsNullOrWhiteSpace(title) ? "Untitled" : title.Trim(),
                ThumbnailPlaceholderKey = imageUrl ?? "",
                Rating = new RatingSummary { Average = 0, Count = 0, MyScore = null },
                LikesCount = 0
            };
            _feed.Insert(0, item);
            _comments[id] = new List<GalleryComment>();
            return Task.FromResult(CloneWithLikeState(item));
        }

        public Task<GalleryComment> PostCommentAsync(string galleryItemId, string body,
            CancellationToken cancellationToken = default)
        {
            var uid = _auth.CurrentSessionUserId ?? "anon";
            if (!_comments.TryGetValue(galleryItemId, out var list))
            {
                list = new List<GalleryComment>();
                _comments[galleryItemId] = list;
            }

            var c = new GalleryComment
            {
                Id = Guid.NewGuid().ToString("N"),
                GalleryItemId = galleryItemId,
                AuthorUserId = uid,
                Body = body,
                CreatedAtUtc = DateTime.UtcNow
            };
            list.Add(c);
            return Task.FromResult(c);
        }
    }
}
