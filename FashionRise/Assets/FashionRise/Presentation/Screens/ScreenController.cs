using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Core;
using FashionRise.Core.Navigation;
using UnityEngine;

namespace FashionRise.Presentation.Screens
{
    public sealed class ScreenController : MonoBehaviour
    {
        [SerializeField] ScreenBase[] screens = Array.Empty<ScreenBase>();

        readonly Dictionary<ScreenId, ScreenBase> _map = new();
        AppServices _app = null!;

        public void Initialize(AppServices app)
        {
            _app = app;
            _map.Clear();
            var list = screens is { Length: > 0 }
                ? screens
                : GetComponentsInChildren<ScreenBase>(true);
            foreach (var s in list)
            {
                if (s == null)
                    continue;
                s.Inject(app);
                if (_map.TryGetValue(s.Id, out var existing) && existing != s)
                {
                    Debug.LogWarning(
                        $"ScreenController: duplicate ScreenId.{s.Id} — keeping '{existing.gameObject.name}', " +
                        $"ignoring '{s.gameObject.name}'. Each screen needs its own script " +
                        $"(e.g. SketchEnhancementScreen on SketchEnhancementScreen object, not SketchCanvasScreen on all).");
                    s.gameObject.SetActive(false);
                    continue;
                }

                _map[s.Id] = s;
                s.gameObject.SetActive(false);
            }
        }

        public async Task ShowAsync(ScreenId id, object? payload, CancellationToken cancellationToken)
        {
            foreach (var kv in _map)
            {
                if (kv.Key == id)
                    await kv.Value.ShowAsync(payload, cancellationToken).ConfigureAwait(true);
                else
                    await kv.Value.HideAsync(cancellationToken).ConfigureAwait(true);
            }
        }
    }
}
