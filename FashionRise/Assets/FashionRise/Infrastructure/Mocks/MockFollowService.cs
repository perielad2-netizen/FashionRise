using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Services;

namespace FashionRise.Infrastructure.Mocks
{
    public sealed class MockFollowService : IFollowService
    {
        readonly IAuthService _auth;
        readonly ConcurrentDictionary<string, HashSet<string>> _byFollower = new(StringComparer.Ordinal);

        public MockFollowService(IAuthService auth) => _auth = auth;

        string? ViewerId => _auth.CurrentSessionUserId;

        public Task FollowAsync(string targetUserId, CancellationToken cancellationToken = default)
        {
            var me = ViewerId;
            if (string.IsNullOrEmpty(me))
                return Task.CompletedTask;
            var set = _byFollower.GetOrAdd(me, _ => new HashSet<string>(StringComparer.Ordinal));
            lock (set)
                set.Add(targetUserId);
            return Task.CompletedTask;
        }

        public Task UnfollowAsync(string targetUserId, CancellationToken cancellationToken = default)
        {
            var me = ViewerId;
            if (string.IsNullOrEmpty(me))
                return Task.CompletedTask;
            if (_byFollower.TryGetValue(me, out var set))
            {
                lock (set)
                    set.Remove(targetUserId);
            }

            return Task.CompletedTask;
        }

        public Task<bool> IsFollowingAsync(string targetUserId, CancellationToken cancellationToken = default)
        {
            var me = ViewerId;
            if (string.IsNullOrEmpty(me))
                return Task.FromResult(false);
            if (!_byFollower.TryGetValue(me, out var set))
                return Task.FromResult(false);
            lock (set)
                return Task.FromResult(set.Contains(targetUserId));
        }

        public Task<IReadOnlyList<string>> GetFollowedUserIdsAsync(CancellationToken cancellationToken = default)
        {
            var me = ViewerId;
            if (string.IsNullOrEmpty(me))
                return Task.FromResult((IReadOnlyList<string>)Array.Empty<string>());
            if (!_byFollower.TryGetValue(me, out var set))
                return Task.FromResult((IReadOnlyList<string>)Array.Empty<string>());
            lock (set)
                return Task.FromResult((IReadOnlyList<string>)set.ToList());
        }
    }
}
