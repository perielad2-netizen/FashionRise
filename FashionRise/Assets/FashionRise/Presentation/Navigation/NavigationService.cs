using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FashionRise.Core.Navigation;
using FashionRise.Presentation.Screens;
using FashionRise.Services;

namespace FashionRise.Presentation.Navigation
{
    public sealed class NavigationService : INavigationService
    {
        private readonly ScreenController _controller;
        private readonly Stack<ScreenId> _stack = new();

        public NavigationService(ScreenController controller)
        {
            _controller = controller;
            Current = ScreenId.Splash;
        }

        public ScreenId Current { get; private set; }

        public async Task NavigateToAsync(ScreenId screen, object? payload = null,
            CancellationToken cancellationToken = default)
        {
            if (Current != ScreenId.Splash && Current != screen)
                _stack.Push(Current);

            Current = screen;
            await _controller.ShowAsync(screen, payload, cancellationToken).ConfigureAwait(true);
        }

        public async Task GoBackAsync(CancellationToken cancellationToken = default)
        {
            if (_stack.Count == 0)
                return;

            Current = _stack.Pop();
            await _controller.ShowAsync(Current, null, cancellationToken).ConfigureAwait(true);
        }
    }
}
