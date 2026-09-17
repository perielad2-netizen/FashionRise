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

            // Repair first: a scene saved before a screen existed must not lose that route.
            var list = new List<ScreenBase>(FashionRiseBootstrapBuilder.EnsureScreens(transform));
            foreach (var serialized in screens)
                if (serialized != null && !list.Contains(serialized))
                    list.Add(serialized);

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
            if (!_map.TryGetValue(id, out var target) || target == null)
            {
                Debug.LogError($"ScreenController: no screen registered for ScreenId.{id}.");
                FrDiag.Fail($"navigate {id}", new InvalidOperationException("screen not registered"));
                return;
            }

            // Activate first: a failure further down must never leave every screen hidden
            // (a blank canvas reads exactly like a crash).
            target.gameObject.SetActive(true);
            FrDiag.Step($"screen → {id}");

            foreach (var kv in _map)
            {
                if (kv.Key == id || kv.Value == null)
                    continue;
                try
                {
                    await kv.Value.HideAsync(cancellationToken).ConfigureAwait(true);
                }
                catch (OperationCanceledException)
                {
                    throw;
                }
                catch (Exception ex)
                {
                    FrDiag.Fail($"hide {kv.Key}", ex);
                }
            }

            try
            {
                await target.ShowAsync(payload, cancellationToken).ConfigureAwait(true);
            }
            catch (OperationCanceledException)
            {
                throw;
            }
            catch (Exception ex)
            {
                FrDiag.Fail($"show {id}", ex);
                Debug.LogError($"FashionRise screen {id} failed while opening: {ex}");
            }
        }
    }
}
