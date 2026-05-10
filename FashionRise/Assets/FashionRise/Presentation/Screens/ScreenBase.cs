using System.Threading;
using System.Threading.Tasks;
using FashionRise.Content;
using FashionRise.Core;
using FashionRise.Core.Navigation;
using UnityEngine;

namespace FashionRise.Presentation.Screens
{
    public abstract class ScreenBase : MonoBehaviour, IScreen
    {
        [SerializeField] protected FashionRiseTheme? theme;

        protected AppServices App { get; private set; } = null!;

        public abstract ScreenId Id { get; }

        public void Inject(AppServices app) => App = app;

        protected FashionRiseTheme ThemeOrDefault => theme != null
            ? theme
            : FashionRiseTheme.CreateRuntimeFallback();

        public virtual Task ShowAsync(object? payload = null, CancellationToken cancellationToken = default)
        {
            gameObject.SetActive(true);
            OnShown(payload);
            return Task.CompletedTask;
        }

        public virtual Task HideAsync(CancellationToken cancellationToken = default)
        {
            gameObject.SetActive(false);
            return Task.CompletedTask;
        }

        protected virtual void OnShown(object? payload)
        {
        }
    }
}
