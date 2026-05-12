using System.Threading;
using System.Threading.Tasks;
using FashionRise.Core.Navigation;

namespace FashionRise.Services
{
    public interface INavigationService
    {
        ScreenId Current { get; }

        Task NavigateToAsync(ScreenId screen, object? payload = null,
            CancellationToken cancellationToken = default);

        /// <summary>Clears the back stack (e.g. after sign-out) then shows <paramref name="screen"/>.</summary>
        Task ResetToAsync(ScreenId screen, object? payload = null,
            CancellationToken cancellationToken = default);

        Task GoBackAsync(CancellationToken cancellationToken = default);
    }
}
